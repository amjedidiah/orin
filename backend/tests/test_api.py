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
    response = await client.get("/health")

    assert response.json() == {
        "status": "ok",
        "meta_api": "ok",
        "open_weights_hosts": ["baseten"],
    }


async def test_chat_streams_server_sent_events(client: AsyncClient):
    response = await client.post("/chat", json={"message": "hello"})

    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert events[0]["type"] == "route"
    assert events[-1]["type"] == "done"


@pytest.mark.parametrize("message", ["", "   ", "\n\t "])
async def test_chat_rejects_a_blank_message(client: AsyncClient, message: str):
    response = await client.post("/chat", json={"message": message})

    assert response.status_code == 422


async def test_chat_trims_the_message(client: AsyncClient, orchestrator: Orchestrator):
    await client.post("/chat", json={"message": "  hello  "})

    [stored] = await orchestrator.store.recent_conversations(1)
    assert stored.prompt == "hello"


async def test_history_lists_stored_conversations(client: AsyncClient):
    await client.post("/chat", json={"message": "hello"})

    [conversation] = (await client.get("/history")).json()

    assert conversation["prompt"] == "hello"
    assert conversation["route"]["target"] == "muse-spark"


async def test_targets_report_availability(client: AsyncClient, gateway):
    gateway.configured_ids.discard(MUSE_SPARK_OPEN)

    targets = {t["id"]: t for t in (await client.get("/targets")).json()}

    assert targets[MUSE_SPARK_OPEN]["available"] is False
    assert targets[MUSE_SPARK_OPEN]["reason"] == "not configured"
    assert targets["muse-spark"]["available"] is True


@pytest.mark.parametrize("name", ["missing.png", "..%2Forin.db", "0" * 32 + ".png"])
async def test_images_only_serves_saved_files(client: AsyncClient, name: str):
    response = await client.get(f"/images/{name}")

    assert response.status_code == 404


@pytest.fixture
def owner_token(orchestrator: Orchestrator) -> str:
    orchestrator.settings.orin_owner_token = SecretStr("s3cret-token")
    return "s3cret-token"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/chat"),
        ("GET", "/history"),
        ("GET", "/targets"),
        ("GET", f"/images/{'0' * 32}.png"),
    ],
)
async def test_owner_token_guards_data_routes(
    client: AsyncClient, owner_token: str, method: str, path: str
):
    response = await client.request(method, path, json={"message": "hi"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_wrong_owner_token_is_rejected(client: AsyncClient, owner_token: str):
    response = await client.get("/history", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401


async def test_owner_token_accepted_as_bearer_header(client: AsyncClient, owner_token: str):
    response = await client.get("/history", headers={"Authorization": f"Bearer {owner_token}"})

    assert response.status_code == 200


async def test_owner_token_accepted_as_cookie(client: AsyncClient, owner_token: str):
    client.cookies.set("orin_owner_token", owner_token)

    response = await client.get("/targets")

    assert response.status_code == 200


async def test_health_stays_public_with_owner_token(client: AsyncClient, owner_token: str):
    response = await client.get("/health")

    assert response.status_code == 200
