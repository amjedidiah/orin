# Orin backend

Python + FastAPI. See the repository README for what Orin does.

```sh
uv sync                                  # install
cp .env.example .env                     # then fill in MODEL_API_KEY
uv run orin                              # serve on http://127.0.0.1:8000
uv run pytest                            # tests
uv run ruff check . && uv run ruff format --check . && uv run pyright
uv run python scripts/smoke_spark.py     # one live Muse Spark call
uv run python scripts/eval_router.py     # live router accuracy on evals/router_cases.json
```
