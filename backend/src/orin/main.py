"""FastAPI application."""

import json
import re
import secrets
from collections.abc import AsyncIterator
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StringConstraints

from orin.availability import Availability
from orin.chat import Orchestrator
from orin.config import Settings, get_settings
from orin.db import Store, make_store
from orin.gateway import HealthStatus, ModelGateway
from orin.registry import MODELS
from orin.security import (
    MIN_OWNER_TOKEN_LENGTH,
    SESSION_SECONDS,
    SecurityHeaders,
    client_key,
    issue_session,
    session_cookie_name,
    session_is_valid,
    uses_https,
)

IMAGE_NAME = re.compile(r"^[0-9a-f]{32}\.png$")

LOGIN_ATTEMPTS = 10
LOGIN_WINDOW_SECONDS = 15 * 60
DEMO_CALLS_PER_CLIENT = 20
DEMO_CLIENT_WINDOW_SECONDS = 60 * 60
DEMO_CALLS_PER_DAY = 300
DAY_SECONDS = 24 * 60 * 60


# The API docs are off: nothing uses them, and they'd map the API for anyone who finds them.
app = FastAPI(title="Orin", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SecurityHeaders)


def build_orchestrator() -> Orchestrator:
    settings = get_settings()
    gateway = ModelGateway(settings)
    database_url = settings.database_url.get_secret_value() if settings.database_url else None
    store = make_store(database_url, settings.database_path)
    return Orchestrator(settings, gateway, store, Availability(gateway))


async def get_orchestrator(request: Request) -> Orchestrator:
    # Built on the first request rather than in a lifespan hook: serverless hosts such as
    # Vercel don't guarantee ASGI startup events. Tests set `app.state.orchestrator` directly.
    # Async so it runs on the event loop: with no await between the check and the assignment,
    # overlapping first requests can't each build a store (and a connection pool).
    state = request.app.state
    if getattr(state, "orchestrator", None) is None:
        state.orchestrator = build_orchestrator()
    return state.orchestrator


OrchestratorDep = Annotated[Orchestrator, Depends(get_orchestrator)]


def owner_secret(settings: Settings) -> str | None:
    """The token that protects this instance, or None when it is deliberately open."""
    token = settings.orin_owner_token
    if token is None:
        if settings.orin_public_demo or (settings.orin_local_open and not settings.vercel):
            return None
        raise HTTPException(status_code=503, detail="ORIN_OWNER_TOKEN is not set")
    secret = token.get_secret_value()
    if len(secret) < MIN_OWNER_TOKEN_LENGTH:
        raise HTTPException(
            status_code=503,
            detail=f"ORIN_OWNER_TOKEN must be at least {MIN_OWNER_TOKEN_LENGTH} characters",
        )
    return secret


def require_owner(request: Request, orchestrator: OrchestratorDep) -> None:
    settings = orchestrator.settings
    secret = owner_secret(settings)
    if secret is None:
        return
    session = request.cookies.get(session_cookie_name(uses_https(request, settings)))
    if session is None or not session_is_valid(session, secret):
        raise HTTPException(
            status_code=401,
            detail="owner session required",
            headers={"WWW-Authenticate": "Cookie"},
        )


async def enforce_limit(store: Store, key: str, limit: int, window_seconds: int) -> None:
    if not await store.hit_rate_limit(key, limit, window_seconds):
        raise HTTPException(
            status_code=429,
            detail="too many requests",
            headers={"Retry-After": str(window_seconds)},
        )


async def limit_public_demo(request: Request, orchestrator: OrchestratorDep) -> None:
    """Model calls cost money, so an open demo gets a per-client limit and a daily cap."""
    settings = orchestrator.settings
    if not settings.orin_public_demo:
        return
    store = orchestrator.store
    client = client_key(request, settings)
    await enforce_limit(store, f"demo:{client}", DEMO_CALLS_PER_CLIENT, DEMO_CLIENT_WINDOW_SECONDS)
    await enforce_limit(store, "demo:all", DEMO_CALLS_PER_DAY, DAY_SECONDS)


public = APIRouter(prefix="/api")
protected = APIRouter(prefix="/api", dependencies=[Depends(require_owner)])


class SessionStatus(BaseModel):
    required: bool


class SessionRequest(BaseModel):
    token: Annotated[str, StringConstraints(min_length=1, max_length=512)]


@public.get("/session")
async def session_status(orchestrator: OrchestratorDep) -> SessionStatus:
    return SessionStatus(required=owner_secret(orchestrator.settings) is not None)


@public.post("/session", status_code=204)
async def create_session(
    body: SessionRequest, request: Request, orchestrator: OrchestratorDep
) -> Response:
    """Swap the owner token for an HttpOnly session cookie that page scripts can't read."""
    settings = orchestrator.settings
    response = Response(status_code=204)
    secret = owner_secret(settings)
    if secret is None:
        return response
    # Counted before the comparison, so a correct guess past the limit is refused too.
    await enforce_limit(
        orchestrator.store,
        f"login:{client_key(request, settings)}",
        LOGIN_ATTEMPTS,
        LOGIN_WINDOW_SECONDS,
    )
    if not secrets.compare_digest(body.token.encode(), secret.encode()):
        raise HTTPException(status_code=401, detail="that key didn't fit")
    secure = uses_https(request, settings)
    response.set_cookie(
        session_cookie_name(secure),
        issue_session(secret),
        max_age=SESSION_SECONDS,
        path="/",
        secure=secure,
        httponly=True,
        samesite="strict",
    )
    return response


@public.delete("/session", status_code=204)
async def end_session(request: Request, orchestrator: OrchestratorDep) -> Response:
    secure = uses_https(request, orchestrator.settings)
    response = Response(status_code=204)
    response.delete_cookie(
        session_cookie_name(secure), path="/", secure=secure, httponly=True, samesite="strict"
    )
    return response


class HealthResponse(BaseModel):
    status: Literal["ok"]
    meta_api: HealthStatus
    open_weights_hosts: list[str]


@public.get("/health")
async def health(orchestrator: OrchestratorDep) -> HealthResponse:
    gateway = orchestrator.gateway
    return HealthResponse(
        status="ok",
        meta_api=await gateway.meta_api_status(),
        open_weights_hosts=gateway.open_weights_host_names(),
    )


class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]


@protected.post("/chat", dependencies=[Depends(limit_public_demo)])
async def chat(body: ChatRequest, orchestrator: OrchestratorDep) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        async for event in orchestrator.chat(body.message):
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@protected.get("/history")
async def history(
    orchestrator: OrchestratorDep, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[dict]:
    # Demo visitors share one store, so one visitor's prompts must never reach another.
    if orchestrator.settings.orin_public_demo:
        return []
    conversations = await orchestrator.store.recent_conversations(limit)
    return [conversation.__dict__ for conversation in conversations]


class TargetStatus(BaseModel):
    id: str
    name: str
    output: str
    cost: str
    strengths: list[str]
    available: bool
    reason: str | None


@protected.get("/targets")
async def targets(orchestrator: OrchestratorDep) -> list[TargetStatus]:
    result = []
    for model in MODELS.values():
        status = orchestrator.availability.status(model.id)
        result.append(
            TargetStatus(
                id=model.id,
                name=model.name,
                output=model.output,
                cost=model.cost,
                strengths=list(model.strengths),
                available=status.available,
                reason=status.reason,
            )
        )
    return result


@protected.get("/images/{name}")
async def image(name: str, request: Request, orchestrator: OrchestratorDep) -> Response:
    if not IMAGE_NAME.match(name):
        raise HTTPException(status_code=404, detail="image not found")
    # Images never change once saved, so the name is the ETag. `no-cache` makes the browser
    # revalidate every time, which re-runs the owner check; an unchanged image costs a 304.
    # The lookup comes first: a missing image is a 404 even for a cached ETag.
    data = await orchestrator.store.load_image(name)
    if data is None:
        raise HTTPException(status_code=404, detail="image not found")
    headers = {"Cache-Control": "private, no-cache", "ETag": f'"{name}"'}
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    return Response(data, media_type="image/png", headers=headers)


app.include_router(public)
app.include_router(protected)

# In production the same process serves the built web app (`web/dist`) at `/`.
_web_dist = get_settings().orin_web_dist
if _web_dist is not None and _web_dist.is_dir():
    app.mount("/", StaticFiles(directory=_web_dist, html=True), name="web")
