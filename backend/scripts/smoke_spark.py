"""Manual check: send one prompt to Muse Spark through the Responses API.

Run from `backend/`: `uv run python scripts/smoke_spark.py`
"""

import asyncio

from orin.config import get_settings
from orin.gateway import ModelGateway
from orin.registry import MUSE_SPARK


async def main() -> None:
    gateway = ModelGateway(get_settings())
    stream = await gateway.open_text_stream(
        MUSE_SPARK,
        "Answer in one short sentence.",
        "What is Orin's job as a personal AI router?",
    )
    async for chunk in stream.chunks:
        print(chunk, end="", flush=True)
    print(f"\n(served by {stream.served_by})")


if __name__ == "__main__":
    asyncio.run(main())
