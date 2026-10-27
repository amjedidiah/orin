"""Storage: the append-only event log, the prompt history derived from it, and images.

Two backends with one interface: SQLite for local development and tests, Postgres (Neon)
when `DATABASE_URL` is set, e.g. on Vercel where there is no persistent disk. Both
prepare their schema on first use, so nothing depends on app startup hooks.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import aiosqlite
import asyncpg

SQLITE_SCHEMA = """
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
CREATE TABLE IF NOT EXISTS images (
    name TEXT PRIMARY KEY,
    data BLOB NOT NULL,
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

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    cursor BIGSERIAL PRIMARY KEY,
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
    event_cursor BIGINT NOT NULL REFERENCES events(cursor),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS images (
    name TEXT PRIMARY KEY,
    data BYTEA NOT NULL,
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
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS summaries (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    from_cursor BIGINT NOT NULL,
    to_cursor BIGINT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Conversation:
    id: str
    number: int
    source: str
    prompt: str
    response: str
    route: dict[str, Any]
    steps: list[dict[str, Any]]
    created_at: str


def now() -> str:
    return datetime.now(UTC).isoformat()


def _conversation(row: Any) -> Conversation:
    """`row` is an aiosqlite.Row or an asyncpg.Record; both support row["column"]."""
    return Conversation(
        id=row["id"],
        number=row["event_cursor"],
        source=row["source"],
        prompt=row["prompt"],
        response=row["response"],
        route=json.loads(row["route"]),
        steps=json.loads(row["steps"]),
        created_at=row["created_at"],
    )


class Store(Protocol):
    async def init(self) -> None: ...

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
        ...

    async def recent_conversations(self, limit: int) -> list[Conversation]:
        """Most recent first."""
        ...

    async def save_image(self, name: str, data: bytes) -> None: ...

    async def load_image(self, name: str) -> bytes | None: ...


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._ready = False

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        if not self._ready:
            await self.init()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            yield db

    async def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SQLITE_SCHEMA)
            await db.commit()
        self._ready = True

    async def save_conversation(
        self,
        conversation_id: str,
        prompt: str,
        response: str,
        route: dict[str, Any],
        steps: list[dict[str, Any]],
        source: str = "orin",
    ) -> int:
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
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                "SELECT * FROM conversations ORDER BY event_cursor DESC LIMIT ?", (limit,)
            )
        return [_conversation(row) for row in rows]

    async def save_image(self, name: str, data: bytes) -> None:
        async with self._connect() as db:
            await db.execute(
                "INSERT INTO images (name, data, created_at) VALUES (?, ?, ?)",
                (name, data, now()),
            )
            await db.commit()

    async def load_image(self, name: str) -> bytes | None:
        async with self._connect() as db:
            rows = list(
                await db.execute_fetchall("SELECT data FROM images WHERE name = ?", (name,))
            )
        return bytes(rows[0][0]) if rows else None


class PostgresStore:
    def __init__(self, dsn: str, server_settings: dict[str, str] | None = None) -> None:
        self.dsn = dsn
        self.server_settings = server_settings
        self._pool: asyncpg.Pool | None = None
        self._lock = asyncio.Lock()

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            async with self._lock:
                if self._pool is None:
                    pool = await asyncpg.create_pool(
                        self.dsn,
                        min_size=0,
                        max_size=5,
                        # Neon's pooled endpoint runs PgBouncer, which can't share
                        # prepared statements across server connections.
                        statement_cache_size=0,
                        server_settings=self.server_settings,
                    )
                    try:
                        async with pool.acquire() as connection:
                            await connection.execute(POSTGRES_SCHEMA)
                    except BaseException:
                        # Don't leak a pool per request while the schema keeps failing.
                        await pool.close()
                        raise
                    self._pool = pool
        return self._pool

    async def init(self) -> None:
        await self._get_pool()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def save_conversation(
        self,
        conversation_id: str,
        prompt: str,
        response: str,
        route: dict[str, Any],
        steps: list[dict[str, Any]],
        source: str = "orin",
    ) -> int:
        created_at = now()
        payload = {"conversation_id": conversation_id, "route": route, "steps": steps}
        pool = await self._get_pool()
        async with pool.acquire() as connection, connection.transaction():
            event_cursor = await connection.fetchval(
                "INSERT INTO events (type, source, payload, created_at)"
                " VALUES ($1, $2, $3, $4) RETURNING cursor",
                "conversation",
                source,
                json.dumps(payload),
                created_at,
            )
            await connection.execute(
                "INSERT INTO conversations"
                " (id, source, prompt, response, route, steps, event_cursor, created_at)"
                " VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                conversation_id,
                source,
                prompt,
                response,
                json.dumps(route),
                json.dumps(steps),
                event_cursor,
                created_at,
            )
        return int(event_cursor)

    async def recent_conversations(self, limit: int) -> list[Conversation]:
        pool = await self._get_pool()
        rows = await pool.fetch(
            "SELECT * FROM conversations ORDER BY event_cursor DESC LIMIT $1", limit
        )
        return [_conversation(row) for row in rows]

    async def save_image(self, name: str, data: bytes) -> None:
        pool = await self._get_pool()
        await pool.execute(
            "INSERT INTO images (name, data, created_at) VALUES ($1, $2, $3)", name, data, now()
        )

    async def load_image(self, name: str) -> bytes | None:
        pool = await self._get_pool()
        data = await pool.fetchval("SELECT data FROM images WHERE name = $1", name)
        return bytes(data) if data is not None else None


def make_store(database_url: str | None, sqlite_path: Path) -> Store:
    if database_url:
        return PostgresStore(database_url)
    return SQLiteStore(sqlite_path)
