"""Browser-facing protections: the owner session cookie, client keys and response headers."""

import hashlib
import hmac
import ipaddress
import re
import time

from fastapi import Request
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from orin.config import Settings

MIN_OWNER_TOKEN_LENGTH = 32
SESSION_SECONDS = 60 * 60 * 24 * 30

_SESSION_VALUE = re.compile(r"^(\d{1,12})\.([0-9a-f]{64})$")

# Mirrored in the web service's `headers` in vercel.json; a test keeps the two in step.
# Remote images are blocked so model output can't leak data through an image URL.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "font-src 'self'; connect-src 'self'; manifest-src 'self'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def uses_https(request: Request, settings: Settings) -> bool:
    return settings.vercel or request.url.scheme == "https"


def session_cookie_name(secure: bool) -> str:
    # Browsers only accept the __Host- prefix on Secure cookies, so plain HTTP can't use it.
    return "__Host-orin_session" if secure else "orin_session"


def _signature(secret: str, expires: int) -> str:
    message = f"orin-session:{expires}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def issue_session(secret: str) -> str:
    """A signed expiry. Changing ORIN_OWNER_TOKEN ends every session, with nothing to store."""
    expires = int(time.time()) + SESSION_SECONDS
    return f"{expires}.{_signature(secret, expires)}"


def session_is_valid(value: str, secret: str) -> bool:
    match = _SESSION_VALUE.match(value)
    if match is None:
        return False
    expires = int(match[1])
    return expires > time.time() and hmac.compare_digest(match[2], _signature(secret, expires))


def client_key(request: Request, settings: Settings) -> str:
    """A hashed client address for rate limits, so raw IPs are never stored.

    Vercel overwrites X-Forwarded-For and puts the client first; elsewhere the header is
    client-controlled, so only the socket address counts. IPv6 is grouped by /64, the block
    one customer usually controls.
    """
    if settings.vercel:
        host = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    else:
        host = request.client.host if request.client else ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "unknown"
    network = ipaddress.ip_network(f"{address}/64", strict=False) if address.version == 6 else host
    return hashlib.sha256(str(network).encode()).hexdigest()


class SecurityHeaders:
    """Pure ASGI, so it never buffers the chat stream."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
                if scope["path"].startswith("/api/"):
                    headers.setdefault("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, send_with_headers)
