from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

import orin.main as app_module
from orin.llm import NotConfiguredError


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app_module.app), base_url="http://test"
    ) as c:
        yield c


def fake_meta_client(list_models: AsyncMock) -> MagicMock:
    meta = MagicMock()
    meta.models.list = list_models
    return meta


async def test_health_without_api_key(client, monkeypatch):
    def not_configured():
        raise NotConfiguredError("MODEL_API_KEY is not set")

    monkeypatch.setattr(app_module, "get_meta_client", not_configured)

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "meta_api": "not_configured"}


async def test_health_with_reachable_meta_api(client, monkeypatch):
    monkeypatch.setattr(app_module, "get_meta_client", lambda: fake_meta_client(AsyncMock()))

    response = await client.get("/health")

    assert response.json()["meta_api"] == "ok"


async def test_health_with_failing_meta_api(client, monkeypatch):
    failing = AsyncMock(side_effect=RuntimeError("connection refused"))
    monkeypatch.setattr(app_module, "get_meta_client", lambda: fake_meta_client(failing))

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["meta_api"] == "error"
