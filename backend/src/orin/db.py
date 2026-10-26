"""SQLite storage: the append-only event log and the prompt history derived from it."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    cursor INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    source TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    route TEXT NOT NULL,
    steps TEXT NOT NULL,
    event_cursor INTEGER NOT NULL REFERENCES events(cursor),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profile (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    source_event_cursors TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS summaries (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    from_cursor INTEGER NOT NULL,
    to_cursor INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Conversation:
    id: str
    source: str
    prompt: str
    response: str
    route: dict[str, Any]
    steps: list[dict[str, Any]]
    created_at: str


def now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            yield db

    async def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self._connect() as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def save_conversation(
        self,
        conversation_id: str,
        prompt: str,
        response: str,
        route: dict[str, Any],
        steps: list[dict[str, Any]],
        source: str = "orin",
    ) -> int:
        """Append a `conversation` event and the prompt-history row derived from it."""
        created_at = now()
        payload = {"conversation_id": conversation_id, "route": route, "steps": steps}
        async with self._connect() as db:
            cursor = await db.execute(
                "INSERT INTO events (type, source, payload, created_at) VALUES (?, ?, ?, ?)",
                ("conversation", source, json.dumps(payload), created_at),
            )
            event_cursor = cursor.lastrowid
            assert event_cursor is not None
            await db.execute(
                "INSERT INTO conversations"
                " (id, source, prompt, response, route, steps, event_cursor, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    conversation_id,
                    source,
                    prompt,
                    response,
                    json.dumps(route),
                    json.dumps(steps),
                    event_cursor,
                    created_at,
                ),
            )
            await db.commit()
        return event_cursor

    async def recent_conversations(self, limit: int) -> list[Conversation]:
        """Most recent first."""
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                "SELECT * FROM conversations ORDER BY event_cursor DESC LIMIT ?", (limit,)
            )
        return [
            Conversation(
                id=row["id"],
                source=row["source"],
                prompt=row["prompt"],
                response=row["response"],
                route=json.loads(row["route"]),
                steps=json.loads(row["steps"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
