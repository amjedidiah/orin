import json

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from orin.chat import Orchestrator
from orin.main import app
from orin.registry import MUSE_SPARK_OPEN


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


@pytest.fixture
def owner_token(orchestrator: Orchestrator) -> str:
    orchestrator.settings.orin_owner_token = SecretStr("s3cret-token")
    return "s3cret-token"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/chat"),
        ("GET", "/api/history"),
        ("GET", "/api/targets"),
        ("GET", f"/api/images/{'0' * 32}.png"),
    ],
)
async def test_owner_token_guards_data_routes(
    client: AsyncClient, owner_token: str, method: str, path: str
):
    response = await client.request(method, path, json={"message": "hi"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_wrong_owner_token_is_rejected(client: AsyncClient, owner_token: str):
    response = await client.get("/api/history", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401


async def test_owner_token_accepted_as_bearer_header(client: AsyncClient, owner_token: str):
    response = await client.get("/api/history", headers={"Authorization": f"Bearer {owner_token}"})

    assert response.status_code == 200


async def test_owner_token_accepted_as_cookie(client: AsyncClient, owner_token: str):
    client.cookies.set("orin_owner_token", owner_token)

    response = await client.get("/api/targets")

    assert response.status_code == 200


async def test_hosted_instance_without_owner_token_stays_locked(
    client: AsyncClient, orchestrator: Orchestrator
):
    orchestrator.settings.vercel = True

    response = await client.get("/api/history")

    assert response.status_code == 503


async def test_hosted_public_demo_opens_without_owner_token(
    client: AsyncClient, orchestrator: Orchestrator
):
    orchestrator.settings.vercel = True
    orchestrator.settings.orin_public_demo = True

    response = await client.get("/api/history")

    assert response.status_code == 200


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
    assert again.status_code == 304


async def test_missing_image_is_404_even_with_a_cached_etag(client: AsyncClient):
    name = "c" * 32 + ".png"

    response = await client.get(f"/api/images/{name}", headers={"If-None-Match": f'"{name}"'})

    assert response.status_code == 404


async def test_cached_image_still_needs_the_owner_token(client: AsyncClient, owner_token: str):
    name = "b" * 32 + ".png"

    response = await client.get(f"/api/images/{name}", headers={"If-None-Match": f'"{name}"'})

    assert response.status_code == 401
