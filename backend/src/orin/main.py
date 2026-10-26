"""FastAPI application."""

import json
import re
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, StringConstraints

from orin.availability import Availability
from orin.chat import Orchestrator
from orin.config import get_settings
from orin.db import Store
from orin.gateway import HealthStatus, ModelGateway
from orin.registry import MODELS

IMAGE_NAME = re.compile(r"^[0-9a-f]{32}\.png$")
OWNER_COOKIE = "orin_owner_token"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    gateway = ModelGateway(settings)
    store = Store(settings.database_path)
    await store.init()
    app.state.gateway = gateway
    app.state.store = store
    app.state.orchestrator = Orchestrator(settings, gateway, store, Availability(gateway))
    yield


app = FastAPI(title="Orin", lifespan=lifespan)


def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator


OrchestratorDep = Annotated[Orchestrator, Depends(get_orchestrator)]


def presented_token(request: Request) -> str | None:
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and credentials:
        return credentials
    # Browsers can't add headers to <img src>, so the web app also sends the token as a cookie.
    return request.cookies.get(OWNER_COOKIE)


def require_owner(request: Request, orchestrator: OrchestratorDep) -> None:
    """Enforce ORIN_OWNER_TOKEN when it is set; an unset token leaves the API open."""
    expected = orchestrator.settings.orin_owner_token
    if expected is None:
        return
    token = presented_token(request)
    if token is None or not secrets.compare_digest(
        token.encode(), expected.get_secret_value().encode()
    ):
        raise HTTPException(
            status_code=401,
            detail="owner token required",
            headers={"WWW-Authenticate": "Bearer"},
        )


protected = APIRouter(dependencies=[Depends(require_owner)])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    meta_api: HealthStatus
    open_weights_hosts: list[str]


@app.get("/health")
async def health(orchestrator: OrchestratorDep) -> HealthResponse:
    gateway = orchestrator.gateway
    return HealthResponse(
        status="ok",
        meta_api=await gateway.meta_api_status(),
        open_weights_hosts=gateway.open_weights_host_names(),
    )


class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]


@protected.post("/chat")
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
async def image(name: str, orchestrator: OrchestratorDep) -> FileResponse:
    path = orchestrator.settings.images_dir / name
    if not IMAGE_NAME.match(name) or not path.is_file():
        raise HTTPException(status_code=404, detail="image not found")
    return FileResponse(path, media_type="image/png")


app.include_router(protected)
