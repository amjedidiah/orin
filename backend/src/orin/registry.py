"""The models Orin can route to."""

from dataclasses import dataclass
from typing import Literal

MUSE_SPARK = "muse-spark"
MUSE_IMAGE = "muse-image"
MUSE_SPARK_OPEN = "muse-spark-open"


@dataclass(frozen=True)
class ModelTarget:
    id: str
    name: str
    output: Literal["text", "image"]
    cost: Literal["paid", "free"]
    strengths: tuple[str, ...]


MODELS: dict[str, ModelTarget] = {
    target.id: target
    for target in (
        ModelTarget(
            id=MUSE_SPARK,
            name="Muse Spark",
            output="text",
            cost="paid",
            strengths=(
                "multi-step reasoning",
                "long-form writing (more than a paragraph)",
                "code",
                "analysis",
                "planning",
            ),
        ),
        ModelTarget(
            id=MUSE_SPARK_OPEN,
            name="Muse Spark Open",
            output="text",
            cost="free",
            strengths=(
                "quick answers",
                "short writing (a few sentences at most)",
                "summaries",
                "rewriting and translation",
            ),
        ),
        ModelTarget(
            id=MUSE_IMAGE,
            name="Muse Image",
            output="image",
            cost="paid",
            strengths=("image generation", "banners and illustrations"),
        ),
    )
}
