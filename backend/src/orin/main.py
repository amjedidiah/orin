"""FastAPI application."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from orin.llm import NotConfiguredError, get_meta_client

app = FastAPI(title="Orin")

ProviderStatus = Literal["ok", "error", "not_configured"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    meta_api: ProviderStatus


async def check_meta_api() -> ProviderStatus:
    try:
        client = get_meta_client()
    except NotConfiguredError:
        return "not_configured"
    try:
        await client.models.list()
    except Exception:
        return "error"
    return "ok"


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", meta_api=await check_meta_api())
