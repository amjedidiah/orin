# AGENTS.md

Guidance for coding agents working in this repository.

## Project

Orin is a personal AI proxy: one context store shared across many AI agents, with Meta's Muse models as the planner, router, synthesizer and summarizer.

Planned stack:

- Backend: Python + FastAPI, managed with `uv`
- Context store: SQLite via `aiosqlite`
- Models: Meta Model API (`https://api.meta.ai/v1`) through the `openai` SDK; Muse Spark Open on Baseten as the open-weights host
- Frontend: React + Vite + TypeScript

## Rules

- Commit or push only when the maintainer asks.
- No AI or tool attribution in commits, PRs, code or docs (no co-author trailers, no "generated with" lines).
- Never commit secrets. Keys live in `.env`; `.env.example` holds empty placeholders.
- Planning files are gitignored on purpose. Never force-add ignored files.
- Talk to outside AI vendors only through their official APIs or protocols. No scraping, UI automation or private endpoints.
- Use only code, data and assets we have the rights to: permissively licensed dependencies and icons, no vendor logos.
- Use synthetic data for demos and tests. No real personal data.

## Model IDs

- Baseten: use `meta-models/muse-spark-open-1026`, not `meta-models/muse-spark-open` from Baseten's docs.
- Check every other model ID against Meta's official model list before using it.
