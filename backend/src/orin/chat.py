"""One chat turn: route, run each step down the fallback chain, store the result."""

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from orin.availability import Availability, reason_for
from orin.config import Settings
from orin.db import Conversation, Store
from orin.gateway import Gateway, ProviderError
from orin.registry import MODELS, MUSE_IMAGE, MUSE_SPARK, MUSE_SPARK_OPEN
from orin.router import Step, route

Event = dict[str, Any]

logger = logging.getLogger(__name__)

CONTEXT_TURNS = 5
CONTEXT_CHARS = 500

PERSONA = """You are Orin, the user's personal AI agent. You were picked for this step because \
it fits your strengths. Answer the task directly. Use the recent context only when it is relevant.

Recent context:
{context}"""


@dataclass
class StepResult:
    target: str
    served_by: str | None = None
    output: str = ""
    image_url: str | None = None
    fallbacks: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None

    def record(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "served_by": self.served_by,
            "output": self.output,
            "image_url": self.image_url,
            "fallbacks": self.fallbacks,
            "error": self.error,
        }


def format_context(conversations: list[Conversation]) -> str:
    def clip(text: str) -> str:
        return text if len(text) <= CONTEXT_CHARS else text[:CONTEXT_CHARS] + "…"

    turns = [f"User: {clip(c.prompt)}\nOrin: {clip(c.response)}" for c in reversed(conversations)]
    return "\n\n".join(turns)


def fallback_chain(target_id: str, mode: str) -> list[str]:
    if MODELS[target_id].output == "image":
        return [MUSE_IMAGE]
    tail = [MUSE_SPARK, MUSE_SPARK_OPEN] if mode == "spark" else [MUSE_SPARK_OPEN]
    return list(dict.fromkeys([target_id, *tail]))


class Orchestrator:
    def __init__(
        self, settings: Settings, gateway: Gateway, store: Store, availability: Availability
    ) -> None:
        self.settings = settings
        self.gateway = gateway
        self.store = store
        self.availability = availability

    async def chat(self, message: str) -> AsyncIterator[Event]:
        conversation_id = uuid.uuid4().hex
        context = format_context(await self.store.recent_conversations(CONTEXT_TURNS))

        decision = await route(self.gateway, message, context, self.availability.available_ids())
        yield {"type": "route", **decision.model_dump()}

        results: list[StepResult] = []
        previous = ""
        for index, step in enumerate(decision.steps):
            result = StepResult(target=step.target)
            results.append(result)
            async for event in self._run_step(index, step, previous, context, result):
                yield event
            if result.error:
                break
            previous = result.output

        response = "\n\n".join(
            r.output or f"[image: {r.image_url}]" for r in results if not r.error
        )
        number = await self.store.save_conversation(
            conversation_id,
            prompt=message,
            response=response,
            route=decision.model_dump(),
            steps=[r.record() for r in results],
        )
        yield {"type": "done", "conversation_id": conversation_id, "number": number}

    async def _run_step(
        self, index: int, step: Step, previous: str, context: str, result: StepResult
    ) -> AsyncIterator[Event]:
        chain = fallback_chain(step.target, self.settings.orin_route_fallback)
        for position, candidate in enumerate(chain):
            following = chain[position + 1] if position + 1 < len(chain) else None
            status = self.availability.status(candidate)
            if not status.available:
                event = self._fallback(index, candidate, following, status.reason or "", result)
                if event:
                    yield event
                continue
            try:
                async for event in self._execute(index, candidate, step, previous, context, result):
                    yield event
                return
            except ProviderError as error:
                logger.warning("%s failed (%s): %s", candidate, error.kind, error)
                self.availability.record_failure(candidate, error)
                if result.output:
                    # Already streamed part of an answer; switching models would garble it.
                    result.error = (
                        f"{MODELS[candidate].name} failed mid-answer ({reason_for(error)})"
                    )
                    yield {"type": "step_error", "index": index, "reason": result.error}
                    return
                event = self._fallback(index, candidate, following, reason_for(error), result)
                if event:
                    yield event
        result.error = self._exhausted_message(step.target)
        yield {"type": "step_error", "index": index, "reason": result.error}

    def _fallback(
        self, index: int, failed: str, following: str | None, reason: str, result: StepResult
    ) -> Event | None:
        if following is None:
            return None
        record = {"from": failed, "to": following, "reason": reason}
        result.fallbacks.append(record)
        return {"type": "fallback", "index": index, **record}

    @staticmethod
    def _exhausted_message(target_id: str) -> str:
        if MODELS[target_id].output == "image":
            return "Muse Image is unavailable and no other model can draw images."
        return "No model could answer: every option in the fallback chain is unavailable."

    async def _execute(
        self,
        index: int,
        target_id: str,
        step: Step,
        previous: str,
        context: str,
        result: StepResult,
    ) -> AsyncIterator[Event]:
        model = MODELS[target_id]
        result.target = target_id
        if model.output == "image":
            image = await self.gateway.generate_image(previous or step.instruction)
            result.served_by = "Meta Model API"
            result.image_url = await self._save_image(image)
            yield self._step_start(index, target_id, result.served_by)
            yield {"type": "image", "index": index, "url": result.image_url}
            return

        prompt = step.instruction
        if previous:
            prompt += f"\n\nInput from the previous step:\n{previous}"
        stream = await self.gateway.open_text_stream(
            target_id, PERSONA.format(context=context or "(none yet)"), prompt
        )
        result.served_by = stream.served_by
        yield self._step_start(index, target_id, stream.served_by)
        async for chunk in stream.chunks:
            result.output += chunk
            yield {"type": "token", "index": index, "text": chunk}

    @staticmethod
    def _step_start(index: int, target_id: str, served_by: str) -> Event:
        model = MODELS[target_id]
        return {
            "type": "step_start",
            "index": index,
            "target": target_id,
            "name": model.name,
            "cost": model.cost,
            "served_by": served_by,
        }

    async def _save_image(self, image: bytes) -> str:
        name = f"{uuid.uuid4().hex}.png"
        await self.store.save_image(name, image)
        return f"/api/images/{name}"
