"""
Alembic migrations environment.
Supports async PostgreSQL via asyncpg.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# -- Import the Base metadata so Alembic can detect model changes --
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.database import Base
from app.db import models  # noqa: F401 — ensure all models are registered
from app.core.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Return the database URL, converting sqlite for sync use if needed."""
    url = settings.DATABASE_URL
    # Alembic needs a sync URL for certain operations
    if "aiosqlite" in url:
        url = url.replace("+aiosqlite", "")
    if "asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without DB connection."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In 'online' mode, create an async engine and run migrations."""
    # Use the DATABASE_URL from settings, ensuring correct async dialect
    url = settings.DATABASE_URL
    if not ("+aiosqlite" in url or "+asyncpg" in url):
        if "sqlite" in url:
            url = url.replace("sqlite://", "sqlite+aiosqlite://")
        elif "postgresql" in url or "postgres" in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://").replace("postgres://", "postgresql+asyncpg://")

    connectable = async_engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
