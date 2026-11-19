"""Alembic environment: async engine, URL from settings (DATABASE_URL) unless given."""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from spotonfit.config import settings
from spotonfit.db import Base, UTCDateTime

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def render_item(type_, obj, autogen_context):
    """Write our custom column type as a plain timezone-aware DateTime in migrations."""
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def include_name(name, type_, parent_names) -> bool:
    """Ignore LangGraph's checkpointer tables (checkpoints, checkpoint_writes, ...), which
    it creates and migrates itself in the same Postgres database."""
    return not (type_ == "table" and name.startswith("checkpoint"))


def _configure(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        render_item=render_item,
        include_name=include_name,
        compare_type=True,
        **kwargs,
    )


def run_offline() -> None:
    _configure(url=_url(), literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    _configure(connection=connection, render_as_batch=connection.dialect.name == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(_url(), poolclass=pool.NullPool)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
