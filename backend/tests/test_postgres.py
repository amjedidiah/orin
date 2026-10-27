"""PostgresStore against a real database. Skipped unless TEST_DATABASE_URL is set.

Each run works in its own throwaway schema, dropped afterwards, so it never touches the
tables a deployment uses.
"""

import os
import uuid

import asyncpg
import pytest

from orin.db import PostgresStore

DSN = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL not set")


@pytest.fixture
async def store():
    assert DSN
    schema = f"orin_test_{uuid.uuid4().hex[:12]}"
    connection = await asyncpg.connect(DSN, statement_cache_size=0)
    await connection.execute(f'CREATE SCHEMA "{schema}"')
    pg = PostgresStore(DSN, server_settings={"search_path": schema})
    try:
        yield pg
    finally:
        await pg.close()
        await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await connection.close()


async def test_conversations_round_trip_newest_first(store: PostgresStore):
    route = {"target": "muse-spark", "reason": "fits", "alternatives": [], "steps": []}
    first = await store.save_conversation("a", "hello", "hi", route, [{"target": "muse-spark"}])
    second = await store.save_conversation("b", "again", "hey", route, [])

    conversations = await store.recent_conversations(10)

    assert second > first
    assert [c.id for c in conversations] == ["b", "a"]
    assert conversations[1].number == first
    assert conversations[1].route == route
    assert conversations[1].steps == [{"target": "muse-spark"}]


async def test_images_round_trip(store: PostgresStore):
    await store.save_image("f" * 32 + ".png", b"\x89PNG data")

    assert await store.load_image("f" * 32 + ".png") == b"\x89PNG data"
    assert await store.load_image("missing.png") is None
