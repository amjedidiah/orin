"""Manual check: send one prompt to Muse Spark through the Responses API.

Run from `backend/`: `uv run python scripts/smoke_spark.py`
"""

import asyncio

from orin.config import get_settings
from orin.llm import get_meta_client


async def main() -> None:
    response = await get_meta_client().responses.create(
        model=get_settings().router_model,
        input="Reply with one short sentence: what is Orin's job as a personal AI router?",
    )
    print(response.output_text)


if __name__ == "__main__":
    asyncio.run(main())
