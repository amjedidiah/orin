"""Vercel entrypoint: the FastAPI app lives in the `orin` package under `src/`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from orin.main import app

__all__ = ["app"]
