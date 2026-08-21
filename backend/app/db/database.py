"""
Database engine and session management using SQLAlchemy async.
Supports both PostgreSQL (production) and SQLite (development).
"""
from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def _build_engine_kwargs() -> dict:
    """Build engine kwargs appropriate for the database backend."""
    if settings.is_sqlite:
        # SQLite: simpler pool configuration
        return {
            "echo": settings.DB_ECHO,
            "connect_args": {"check_same_thread": False},
        }
    else:
        # PostgreSQL: full pool configuration
        return {
            "echo": settings.DB_ECHO,
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        }


# Async engine — shared across the application
engine = create_async_engine(
    settings.DATABASE_URL,
    **_build_engine_kwargs(),
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncSession:
    """
    FastAPI dependency that yields an async database session.
    Automatically handles commit/rollback and session cleanup.

    Usage:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_db_and_tables() -> None:
    """
    Create all database tables.
    Used in development mode. Production should use Alembic migrations.
    """
    # Import all models to ensure they are registered with Base
    import app.db.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created", url=settings.DATABASE_URL)


async def drop_db_and_tables() -> None:
    """
    Drop all database tables. USE WITH CAUTION.
    Only for test teardown.
    """
    import app.db.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("All database tables dropped")
