import json
from collections.abc import AsyncIterator, Iterable
from pathlib import Path
from typing import Any

import pytest

from orin.availability import Availability
from orin.chat import Orchestrator
from orin.config import Settings
from orin.db import SQLiteStore
from orin.gateway import HealthStatus, ProviderError, TextStream
from orin.registry import MUSE_IMAGE, MUSE_SPARK, MUSE_SPARK_OPEN

SERVED_BY = {MUSE_SPARK: "Meta Model API", MUSE_SPARK_OPEN: "Baseten"}

# A text reply: chunks to stream, or a ProviderError raised before (or during) streaming.
Reply = list[str | ProviderError] | ProviderError


def route_json(target: str, steps: Iterable[tuple[str, str]], reason: str = "best fit") -> str:
    return json.dumps(
        {
            "target": target,
            "reason": reason,
            "alternatives": [],
            "steps": [{"target": t, "instruction": i} for t, i in steps],
        }
    )


class FakeGateway:
    def __init__(self) -> None:
        self.configured_ids = {MUSE_SPARK, MUSE_SPARK_OPEN, MUSE_IMAGE}
        self.route_reply: str | ProviderError = route_json(MUSE_SPARK, [(MUSE_SPARK, "answer")])
        self.text_replies: dict[str, Reply] = {
            MUSE_SPARK: ["Hello", " from Spark"],
            MUSE_SPARK_OPEN: ["Hello", " from Spark Open"],
        }
        self.image_reply: bytes | ProviderError = b"\x89PNG fake"
        self.route_prompts: list[str] = []
        self.text_calls: list[tuple[str, str, str]] = []
        self.image_prompts: list[str] = []

    def configured(self, target_id: str) -> bool:
        return target_id in self.configured_ids

    def open_weights_host_names(self) -> list[str]:
        return ["baseten"] if MUSE_SPARK_OPEN in self.configured_ids else []

    async def meta_api_status(self) -> HealthStatus:
        return "ok" if MUSE_SPARK in self.configured_ids else "not_configured"

    async def route_json(self, instructions: str, prompt: str, schema: Any, name: str) -> str:
        self.route_prompts.append(prompt)
        if isinstance(self.route_reply, ProviderError):
            raise self.route_reply
        return self.route_reply

    async def open_text_stream(self, target_id: str, instructions: str, prompt: str) -> TextStream:
        self.text_calls.append((target_id, instructions, prompt))
        reply = self.text_replies[target_id]
        if isinstance(reply, ProviderError):
            raise reply

        async def chunks() -> AsyncIterator[str]:
            for item in reply:
                if isinstance(item, ProviderError):
                    raise item
                yield item

        return TextStream(served_by=SERVED_BY[target_id], chunks=chunks())

    async def generate_image(self, prompt: str) -> bytes:
        self.image_prompts.append(prompt)
        if isinstance(self.image_reply, ProviderError):
            raise self.image_reply
        return self.image_reply


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, orin_data_dir=tmp_path)  # pyright: ignore[reportCallIssue]


@pytest.fixture
def gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
async def orchestrator(settings: Settings, gateway: FakeGateway, clock: Clock) -> Orchestrator:
    store = SQLiteStore(settings.database_path)
    await store.init()
    return Orchestrator(settings, gateway, store, Availability(gateway, clock))


async def collect(orchestrator: Orchestrator, message: str) -> list[dict[str, Any]]:
    return [event async for event in orchestrator.chat(message)]


def of_type(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [event for event in events if event["type"] == kind]
