import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from orin.chat import Orchestrator
from orin.main import app
from orin.registry import MUSE_SPARK_OPEN
from orin.security import SECURITY_HEADERS, SESSION_SECONDS, session_is_valid


@pytest.fixture
async def client(orchestrator: Orchestrator):
    app.state.orchestrator = orchestrator
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.strip().split("\n\n"):
        data = next(line for line in block.splitlines() if line.startswith("data: "))
        events.append(json.loads(data.removeprefix("data: ")))
    return events


async def test_health(client: AsyncClient):
    response = await client.get("/api/health")

    assert response.json() == {
        "status": "ok",
        "meta_api": "ok",
        "open_weights_hosts": ["baseten"],
    }


async def test_chat_streams_server_sent_events(client: AsyncClient):
    response = await client.post("/api/chat", json={"message": "hello"})

    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert events[0]["type"] == "route"
    assert events[-1]["type"] == "done"


@pytest.mark.parametrize("message", ["", "   ", "\n\t "])
async def test_chat_rejects_a_blank_message(client: AsyncClient, message: str):
    response = await client.post("/api/chat", json={"message": message})

    assert response.status_code == 422


async def test_chat_trims_the_message(client: AsyncClient, orchestrator: Orchestrator):
    await client.post("/api/chat", json={"message": "  hello  "})

    [stored] = await orchestrator.store.recent_conversations(1)
    assert stored.prompt == "hello"


async def test_history_lists_stored_conversations(client: AsyncClient):
    await client.post("/api/chat", json={"message": "hello"})

    [conversation] = (await client.get("/api/history")).json()

    assert conversation["prompt"] == "hello"
    assert conversation["route"]["target"] == "muse-spark"


async def test_targets_report_availability(client: AsyncClient, gateway):
    gateway.configured_ids.discard(MUSE_SPARK_OPEN)

    targets = {t["id"]: t for t in (await client.get("/api/targets")).json()}

    assert targets[MUSE_SPARK_OPEN]["available"] is False
    assert targets[MUSE_SPARK_OPEN]["reason"] == "not configured"
    assert targets["muse-spark"]["available"] is True


@pytest.mark.parametrize("name", ["missing.png", "..%2Forin.db", "0" * 32 + ".png"])
async def test_images_only_serves_saved_files(client: AsyncClient, name: str):
    response = await client.get(f"/api/images/{name}")

    assert response.status_code == 404


OWNER_TOKEN = "synthetic-owner-token-of-32-chars-or-more"


@pytest.fixture
def owner_token(orchestrator: Orchestrator) -> str:
    orchestrator.settings.orin_local_open = False
    orchestrator.settings.orin_owner_token = SecretStr(OWNER_TOKEN)
    return OWNER_TOKEN


async def log_in(client: AsyncClient, token: str = OWNER_TOKEN):
    return await client.post("/api/session", json={"token": token})


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/chat"),
        ("GET", "/api/history"),
        ("GET", "/api/targets"),
        ("GET", f"/api/images/{'0' * 32}.png"),
    ],
)
async def test_owner_session_guards_data_routes(
    client: AsyncClient, owner_token: str, method: str, path: str
):
    response = await client.request(method, path, json={"message": "hi"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Cookie"


async def test_owner_token_itself_opens_nothing_but_the_session_route(
    client: AsyncClient, owner_token: str
):
    bearer = {"Authorization": f"Bearer {owner_token}"}
    client.cookies.set("orin_session", owner_token)

    assert (await client.get("/api/history", headers=bearer)).status_code == 401


async def test_log_in_sets_a_cookie_scripts_cannot_read(client: AsyncClient, owner_token: str):
    response = await log_in(client)

    cookie = response.headers["set-cookie"]
    assert response.status_code == 204
    assert cookie.startswith("orin_session=")
    assert owner_token not in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert (await client.get("/api/targets")).status_code == 200


async def test_hosted_cookie_is_secure_with_a_host_prefix(
    client: AsyncClient, orchestrator: Orchestrator, owner_token: str
):
    orchestrator.settings.vercel = True

    cookie = (await log_in(client)).headers["set-cookie"]

    assert cookie.startswith("__Host-orin_session=")
    assert "Secure" in cookie


async def test_wrong_key_gets_no_session(client: AsyncClient, owner_token: str):
    response = await log_in(client, "wrong")

    assert response.status_code == 401
    assert "set-cookie" not in response.headers


async def test_log_out_ends_the_session(client: AsyncClient, owner_token: str):
    await log_in(client)

    response = await client.delete("/api/session")

    assert response.status_code == 204
    assert (await client.get("/api/targets")).status_code == 401


async def test_rotating_the_owner_token_ends_existing_sessions(
    client: AsyncClient, orchestrator: Orchestrator, owner_token: str
):
    await log_in(client)
    orchestrator.settings.orin_owner_token = SecretStr("another-synthetic-token-32-characters")

    assert (await client.get("/api/targets")).status_code == 401


async def test_expired_session_is_rejected(
    client: AsyncClient, owner_token: str, monkeypatch: pytest.MonkeyPatch
):
    await log_in(client)
    assert (await client.get("/api/targets")).status_code == 200
    # Only the server's clock moves: the test client's cookie jar still sends the cookie.
    later = SimpleNamespace(time=lambda: time.time() + SESSION_SECONDS + 1)
    monkeypatch.setattr("orin.security.time", later)

    assert (await client.get("/api/targets")).status_code == 401


@pytest.mark.parametrize(
    "value", ["", "abc", "9999999999.abc", "9999999999." + "0" * 64, "9" * 5000 + "." + "0" * 64]
)
def test_forged_session_values_fail(value: str):
    assert not session_is_valid(value, OWNER_TOKEN)


async def test_login_attempts_are_limited_even_for_the_right_key(
    client: AsyncClient, owner_token: str
):
    for _ in range(10):
        assert (await log_in(client, "wrong")).status_code == 401

    blocked = await log_in(client)

    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "900"
    assert "set-cookie" not in blocked.headers


async def test_weak_owner_token_locks_the_instance(client: AsyncClient, orchestrator: Orchestrator):
    orchestrator.settings.orin_owner_token = SecretStr("short")

    assert (await client.get("/api/history")).status_code == 503
    assert (await log_in(client, "short")).status_code == 503


async def test_session_status_reports_whether_a_key_is_needed(
    client: AsyncClient, orchestrator: Orchestrator
):
    assert (await client.get("/api/session")).json() == {"required": False}

    orchestrator.settings.orin_owner_token = SecretStr(OWNER_TOKEN)

    assert (await client.get("/api/session")).json() == {"required": True}


async def test_missing_token_locks_any_host_by_default(
    client: AsyncClient, orchestrator: Orchestrator
):
    orchestrator.settings.orin_local_open = False

    assert (await client.get("/api/history")).status_code == 503


async def test_hosted_instance_without_owner_token_stays_locked(
    client: AsyncClient, orchestrator: Orchestrator
):
    orchestrator.settings.vercel = True  # ORIN_LOCAL_OPEN is on in tests and must not count here

    response = await client.get("/api/history")

    assert response.status_code == 503


async def test_hosted_public_demo_opens_without_owner_token(
    client: AsyncClient, orchestrator: Orchestrator
):
    orchestrator.settings.vercel = True
    orchestrator.settings.orin_public_demo = True

    response = await client.get("/api/history")

    assert response.status_code == 200


async def test_public_demo_never_shares_history(client: AsyncClient, orchestrator: Orchestrator):
    await client.post("/api/chat", json={"message": "a private note"})
    orchestrator.settings.orin_public_demo = True

    assert (await client.get("/api/history")).json() == []


async def test_public_demo_limits_each_client(client: AsyncClient, orchestrator: Orchestrator):
    orchestrator.settings.orin_public_demo = True

    for _ in range(20):
        assert (await client.post("/api/chat", json={"message": "hi"})).status_code == 200
    blocked = await client.post("/api/chat", json={"message": "hi"})

    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "3600"


async def test_demo_limit_uses_the_vercel_client_address(
    client: AsyncClient, orchestrator: Orchestrator
):
    orchestrator.settings.vercel = True
    orchestrator.settings.orin_public_demo = True
    first = {"x-forwarded-for": "203.0.113.1, 10.0.0.1"}
    second = {"x-forwarded-for": "203.0.113.2"}

    for _ in range(20):
        await client.post("/api/chat", json={"message": "hi"}, headers=first)

    assert (
        await client.post("/api/chat", json={"message": "hi"}, headers=first)
    ).status_code == 429
    assert (
        await client.post("/api/chat", json={"message": "hi"}, headers=second)
    ).status_code == 200


async def test_forwarded_header_is_ignored_off_vercel(
    client: AsyncClient, orchestrator: Orchestrator
):
    orchestrator.settings.orin_public_demo = True

    for index in range(20):
        headers = {"x-forwarded-for": f"203.0.113.{index}"}
        await client.post("/api/chat", json={"message": "hi"}, headers=headers)
    spoofed = {"x-forwarded-for": "203.0.113.200"}

    assert (
        await client.post("/api/chat", json={"message": "hi"}, headers=spoofed)
    ).status_code == 429


async def test_public_demo_has_a_daily_cap(client: AsyncClient, orchestrator: Orchestrator):
    orchestrator.settings.orin_public_demo = True
    for _ in range(300):
        await orchestrator.store.hit_rate_limit("demo:all", 300, 86400)

    assert (await client.post("/api/chat", json={"message": "hi"})).status_code == 429


async def test_health_stays_public_with_owner_token(client: AsyncClient, owner_token: str):
    response = await client.get("/api/health")

    assert response.status_code == 200


async def test_images_revalidate_through_the_owner_check(
    client: AsyncClient, orchestrator: Orchestrator
):
    name = "a" * 32 + ".png"
    await orchestrator.store.save_image(name, b"\x89PNG data")

    first = await client.get(f"/api/images/{name}")
    again = await client.get(
        f"/api/images/{name}", headers={"If-None-Match": first.headers["etag"]}
    )

    assert first.status_code == 200
    assert first.content == b"\x89PNG data"
    assert first.headers["cache-control"] == "private, no-cache"
    assert first.headers["x-content-type-options"] == "nosniff"
    assert again.status_code == 304


async def test_missing_image_is_404_even_with_a_cached_etag(client: AsyncClient):
    name = "c" * 32 + ".png"

    response = await client.get(f"/api/images/{name}", headers={"If-None-Match": f'"{name}"'})

    assert response.status_code == 404


async def test_cached_image_still_needs_an_owner_session(client: AsyncClient, owner_token: str):
    name = "b" * 32 + ".png"

    response = await client.get(f"/api/images/{name}", headers={"If-None-Match": f'"{name}"'})

    assert response.status_code == 401


async def test_responses_carry_security_headers_and_stay_out_of_caches(client: AsyncClient):
    response = await client.get("/api/health")

    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value
    assert response.headers["cache-control"] == "no-store"


async def test_chat_stream_keeps_its_own_cache_header(client: AsyncClient):
    response = await client.post("/api/chat", json={"message": "hello"})

    assert response.headers["cache-control"] == "no-cache"
    assert "content-security-policy" in response.headers


def test_vercel_serves_the_web_app_the_same_security_headers():
    config = json.loads((Path(__file__).parents[2] / "vercel.json").read_text())
    [rule] = config["services"]["web"]["headers"]

    assert {h["key"]: h["value"] for h in rule["headers"]} == SECURITY_HEADERS


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
async def test_api_docs_are_off(client: AsyncClient, path: str):
    assert (await client.get(path)).status_code == 404
