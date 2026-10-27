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
from orin.config import get_settings
from orin.db import make_store
from orin.gateway import HealthStatus, ModelGateway
from orin.registry import MODELS

IMAGE_NAME = re.compile(r"^[0-9a-f]{32}\.png$")
OWNER_COOKIE = "orin_owner_token"


app = FastAPI(title="Orin")


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


def presented_token(request: Request) -> str | None:
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and credentials:
        return credentials
    # Browsers can't add headers to <img src>, so the web app also sends the token as a cookie.
    return request.cookies.get(OWNER_COOKIE)


def require_owner(request: Request, orchestrator: OrchestratorDep) -> None:
    """Enforce ORIN_OWNER_TOKEN when it is set; an unset token leaves a local API open."""
    settings = orchestrator.settings
    expected = settings.orin_owner_token
    if expected is None:
        if settings.vercel and not settings.orin_public_demo:
            raise HTTPException(status_code=503, detail="ORIN_OWNER_TOKEN is not set")
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


public = APIRouter(prefix="/api")
protected = APIRouter(prefix="/api", dependencies=[Depends(require_owner)])


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
