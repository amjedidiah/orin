# AGENTS.md

Guidance for coding agents working in this repository.

## Project

Orin routes each task to the best-fit AI model or agent, keeps one shared memory and prompt history, and falls back to a free open-weights model. Meta's Muse models do the routing, the model work and the memory.

Stack:

- `backend/`: Python 3.12 + FastAPI, managed with `uv`; package in `src/orin/`, tests in `tests/`
- `web/`: React + Vite + TypeScript, managed with `bun`; `/api/*` is proxied to the backend in development
- Models: Meta Model API (`https://api.meta.ai/v1`) through the `openai` SDK; Muse Spark Open on Baseten as the open-weights host
- Planned: SQLite via `aiosqlite` for the context store; MCP server via the `mcp` SDK

## Commands

```sh
# backend/
uv sync
uv run orin                                            # dev server on :8000
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run pyright

# web/
bun install
bun run dev                                            # dev server on :5173
bun run lint && bun run build
```

CI (`.github/workflows/ci.yml`) runs all of these on every push. Keep it green.

## Rules

- Commit or push only when the maintainer asks.
- Every commit message strictly follows Conventional Commits 1.0.0: `<type>(<optional scope>): <description>`, with `type` one of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`; imperative, lowercase description, no trailing period; optional body and footers; `!` or a `BREAKING CHANGE:` footer for breaking changes.
- After changing files, run a CodeRabbit review against `origin/main` (`coderabbit review --agent --base origin/main --include-untracked`) and fix every valid finding before asking the maintainer to commit. Report findings you judged invalid, with the reason.
- No AI or tool attribution in commits, PRs, code or docs (no co-author trailers, no "generated with" lines).
- Never commit secrets. Keys live in `.env`; `.env.example` holds empty placeholders.
- Planning files are gitignored on purpose. Never force-add ignored files.
- Talk to outside AI vendors only through their official APIs or protocols. No scraping, UI automation or private endpoints.
- Use only code, data and assets we have the rights to: permissively licensed dependencies and icons, no vendor logos.
- Use synthetic data for demos and tests. No real personal data.

## Model IDs

- Baseten: use `meta-models/muse-spark-open-1026`, not `meta-models/muse-spark-open` from Baseten's docs.
- Check every other model ID against Meta's official model list before using it.
