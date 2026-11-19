"""Coach memory: the LangGraph checkpointer that stores each conversation thread
(PRD C-05: the coach remembers the conversation within a day, across restarts).

- Postgres DATABASE_URL -> AsyncPostgresSaver on a small psycopg pool, in the same database
  (its tables are named checkpoint*; Alembic ignores them).
- SQLite DATABASE_URL -> AsyncSqliteSaver in a separate file (CHAT_DB_PATH).
- COACH_MEMORY=memory -> InMemorySaver (lost on restart; used by tests).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.memory import InMemorySaver

from spotonfit.config import settings

log = logging.getLogger(__name__)

# Serialises AsyncPostgresSaver.setup() across workers and instances: concurrent CREATE TABLE
# calls race and fail with UniqueViolation, which crash-looped Cloud Run workers at startup.
_SETUP_LOCK_ID = 7_310_442


def psycopg_url(database_url: str) -> str:
    """postgresql+asyncpg://...?ssl=require -> postgresql://...?sslmode=require (psycopg form)."""
    url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url.replace("ssl=require", "sslmode=require")


@asynccontextmanager
async def open_checkpointer(database_url: str | None = None, mode: str | None = None) -> AsyncIterator[object]:
    url = database_url or settings.database_url
    mode = mode or settings.coach_memory
    if mode == "memory":
        yield InMemorySaver()
        return
    if url.startswith("postgresql"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        kwargs = {"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}
        # check=: Neon suspends idle computes and closes their connections; test each one on
        # checkout instead of handing a dead connection to the coach.
        async with AsyncConnectionPool(
            psycopg_url(url),
            max_size=settings.checkpoint_pool_size,
            kwargs=kwargs,
            open=False,
            check=AsyncConnectionPool.check_connection,
        ) as pool:
            saver = AsyncPostgresSaver(pool)
            async with pool.connection() as conn:
                await conn.execute("SELECT pg_advisory_lock(%s)", (_SETUP_LOCK_ID,))
                try:
                    await saver.setup()
                finally:
                    await conn.execute("SELECT pg_advisory_unlock(%s)", (_SETUP_LOCK_ID,))
            log.info("coach memory: postgres")
            yield saver
        return
    if url.startswith("sqlite"):
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        async with AsyncSqliteSaver.from_conn_string(settings.chat_db_path) as saver:
            await saver.setup()
            log.info("coach memory: sqlite (%s)", settings.chat_db_path)
            yield saver
        return
    log.warning("coach memory: no persistent checkpointer for %s; using in-memory", url.split(":", 1)[0])
    yield InMemorySaver()
