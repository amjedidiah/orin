"""Muse Spark picks the best-fit model for each request."""

import json
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ValidationError

from orin.gateway import Gateway, ProviderError
from orin.registry import MODELS, MUSE_IMAGE, MUSE_SPARK

INSTRUCTIONS = """You are Orin's router. Pick the best-fit model for the user's request.

Models:
{models}

Rules:
- Pick the model whose strengths fit the request best.
- Prefer a free model when it can do the task well.
- An image request needs two steps: first a text model writes a detailed image prompt,
  then the image model draws it.
- Every other request is one step.
- `steps[].instruction` is what that model should do, rewritten as a clear, self-contained task.
- `reason` is one short sentence the user will see, explaining the choice.
- `alternatives` lists other models that could also do it, best first. It may be empty.
"""


class Step(BaseModel):
    target: str
    instruction: str


class RouteDecision(BaseModel):
    target: str
    reason: str
    alternatives: list[str]
    steps: list[Step]
    routed_by: str = "router"


def schema(target_ids: Sequence[str]) -> dict[str, Any]:
    ids = list(target_ids)
    return {
        "type": "object",
        "properties": {
            "target": {"type": "string", "enum": ids},
            "reason": {"type": "string"},
            "alternatives": {"type": "array", "items": {"type": "string", "enum": ids}},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "enum": ids},
                        "instruction": {"type": "string"},
                    },
                    "required": ["target", "instruction"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["target", "reason", "alternatives", "steps"],
        "additionalProperties": False,
    }


def describe(target_ids: Sequence[str]) -> str:
    lines = []
    for target_id in target_ids:
        model = MODELS[target_id]
        lines.append(
            f"- {model.id} ({model.name}, {model.output} output, {model.cost}): "
            + ", ".join(model.strengths)
        )
    return "\n".join(lines)


def default_route(message: str, reason: str) -> RouteDecision:
    return RouteDecision(
        target=MUSE_SPARK,
        reason=reason,
        alternatives=[],
        steps=[Step(target=MUSE_SPARK, instruction=message)],
        routed_by="default",
    )


def is_valid(decision: RouteDecision, target_ids: Sequence[str]) -> bool:
    if not decision.steps or decision.target not in target_ids:
        return False
    if any(step.target not in target_ids for step in decision.steps):
        return False
    # The image model can't write its own prompt, so it never runs first or alone.
    return decision.steps[0].target != MUSE_IMAGE


async def route(
    gateway: Gateway, message: str, context: str, target_ids: Sequence[str]
) -> RouteDecision:
    if not target_ids:
        return default_route(message, "No model is available, so Orin tried Muse Spark.")
    prompt = f"Recent context:\n{context or '(none yet)'}\n\nUser request:\n{message}"
    try:
        raw = await gateway.route_json(
            INSTRUCTIONS.format(models=describe(target_ids)), prompt, schema(target_ids), "route"
        )
        decision = RouteDecision.model_validate(json.loads(raw))
    except ProviderError:
        return default_route(message, "The router was unavailable, so Orin used Muse Spark.")
    except (ValidationError, json.JSONDecodeError):
        return default_route(
            message, "The router's answer was unreadable, so Orin used Muse Spark."
        )
    if not is_valid(decision, target_ids):
        return default_route(message, "The router picked an invalid plan, so Orin used Muse Spark.")
    return decision
