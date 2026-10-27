"""Calls to model providers, behind one interface so tests can swap it out."""

import base64
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import openai
from openai import AsyncOpenAI

from orin.config import Settings
from orin.registry import MUSE_IMAGE, MUSE_SPARK, MUSE_SPARK_OPEN

ErrorKind = Literal[
    "not_configured", "rate_limited", "payment_required", "auth", "server", "timeout", "bad_request"
]


class ProviderError(Exception):
    """A model call failed in a way the fallback chain can act on."""

    def __init__(self, kind: ErrorKind, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.kind: ErrorKind = kind
        self.status = status


def classify(exc: Exception) -> ProviderError:
    if isinstance(exc, ProviderError):
        return exc
    if isinstance(exc, openai.APITimeoutError):
        return ProviderError("timeout", "the request timed out")
    if isinstance(exc, openai.APIConnectionError):
        return ProviderError("server", "could not connect")
    if isinstance(exc, openai.APIStatusError):
        status = exc.status_code
        kind: ErrorKind
        if status == 429:
            kind = "rate_limited"
        elif status == 402:
            kind = "payment_required"
        elif status in (401, 403):
            kind = "auth"
        elif status >= 500:
            kind = "server"
        else:
            kind = "bad_request"
        # The provider's own message goes to the logs only; users see the short reason.
        return ProviderError(kind, f"HTTP {status}: {exc.message}"[:500], status)
    return ProviderError("server", type(exc).__name__)


@dataclass
class TextStream:
    served_by: str
    chunks: AsyncIterator[str]


@dataclass(frozen=True)
class OpenWeightsHost:
    name: str
    client: AsyncOpenAI
    model: str


HealthStatus = Literal["ok", "error", "not_configured"]


class Gateway(Protocol):
    def configured(self, target_id: str) -> bool: ...

    def open_weights_host_names(self) -> list[str]: ...

    async def meta_api_status(self) -> HealthStatus: ...

    async def route_json(
        self, instructions: str, prompt: str, schema: dict[str, Any], name: str
    ) -> str: ...

    async def open_text_stream(
        self, target_id: str, instructions: str, prompt: str
    ) -> TextStream: ...

    async def generate_image(self, prompt: str) -> bytes: ...


class ModelGateway:
    """Real provider calls: the Meta Model API and open-weights hosts."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.meta = (
            AsyncOpenAI(
                base_url=settings.meta_api_base_url,
                api_key=settings.model_api_key.get_secret_value(),
            )
            if settings.model_api_key
            else None
        )
        self.open_weights_hosts = self._build_hosts(settings)

    @staticmethod
    def _build_hosts(settings: Settings) -> Sequence[OpenWeightsHost]:
        available = {
            "baseten": (
                settings.baseten_base_url,
                settings.baseten_api_key,
                settings.baseten_model,
            ),
            "modal": (settings.modal_base_url, settings.modal_api_key, settings.modal_model),
        }
        hosts = []
        for name in (part.strip() for part in settings.open_weights_order.split(",")):
            base_url, key, model = available.get(name, (None, None, ""))
            if base_url and key:
                client = AsyncOpenAI(base_url=base_url, api_key=key.get_secret_value())
                hosts.append(OpenWeightsHost(name, client, model))
        return hosts

    def configured(self, target_id: str) -> bool:
        if target_id in (MUSE_SPARK, MUSE_IMAGE):
            return self.meta is not None
        if target_id == MUSE_SPARK_OPEN:
            return bool(self.open_weights_hosts)
        return False

    def open_weights_host_names(self) -> list[str]:
        return [host.name for host in self.open_weights_hosts]

    async def meta_api_status(self) -> HealthStatus:
        if self.meta is None:
            return "not_configured"
        try:
            # Short timeout, no retries: /health is public and must answer fast.
            await self.meta.with_options(timeout=5.0, max_retries=0).models.list()
        except Exception:
            return "error"
        return "ok"

    def _meta(self) -> AsyncOpenAI:
        if self.meta is None:
            raise ProviderError("not_configured", "MODEL_API_KEY is not set")
        return self.meta

    async def route_json(
        self, instructions: str, prompt: str, schema: dict[str, Any], name: str
    ) -> str:
        try:
            response = await self._meta().responses.create(
                model=self.settings.router_model,
                instructions=instructions,
                input=prompt,
                reasoning={"effort": self.settings.router_reasoning_effort},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": name,
                        "schema": schema,
                        "strict": True,
                    }
                },
            )
        except Exception as exc:
            raise classify(exc) from exc
        return response.output_text

    async def open_text_stream(self, target_id: str, instructions: str, prompt: str) -> TextStream:
        if target_id == MUSE_SPARK:
            return await self._spark_stream(instructions, prompt)
        if target_id == MUSE_SPARK_OPEN:
            return await self._open_weights_stream(instructions, prompt)
        raise ProviderError("bad_request", f"{target_id} does not produce text")

    async def _spark_stream(self, instructions: str, prompt: str) -> TextStream:
        try:
            stream = await self._meta().responses.create(
                model=self.settings.router_model,
                instructions=instructions,
                input=prompt,
                stream=True,
            )
        except Exception as exc:
            raise classify(exc) from exc

        async def chunks() -> AsyncIterator[str]:
            try:
                async for event in stream:
                    if event.type == "response.output_text.delta":
                        yield event.delta
            except Exception as exc:
                raise classify(exc) from exc

        return TextStream(served_by="Meta Model API", chunks=chunks())

    async def _open_weights_stream(self, instructions: str, prompt: str) -> TextStream:
        if not self.open_weights_hosts:
            raise ProviderError("not_configured", "no open-weights host is configured")
        last_error: ProviderError | None = None
        for host in self.open_weights_hosts:
            try:
                stream = await host.client.chat.completions.create(
                    model=host.model,
                    messages=[
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": prompt},
                    ],
                    stream=True,
                )
            except Exception as exc:
                last_error = classify(exc)
                continue
            return TextStream(served_by=host.name.capitalize(), chunks=_chat_chunks(stream))
        assert last_error is not None
        raise last_error

    async def generate_image(self, prompt: str) -> bytes:
        try:
            result = await self._meta().images.generate(
                model=self.settings.image_model, prompt=prompt, n=1
            )
        except Exception as exc:
            raise classify(exc) from exc
        if not result.data or not result.data[0].b64_json:
            raise ProviderError("server", "no image returned")
        return base64.b64decode(result.data[0].b64_json)


async def _chat_chunks(stream: Any) -> AsyncIterator[str]:
    try:
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as exc:
        raise classify(exc) from exc
