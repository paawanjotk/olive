import contextvars
import logging
from typing import AsyncGenerator


import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# Engine and session factory singletons (used by the long-lived API process,
# which runs on a single event loop).
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# Per-run override for the Celery worker. Each task runs in its own fresh event
# loop (asyncio.run), so it can't share the singleton engine — its asyncpg
# connections would be bound to a different loop. The worker sets a per-run,
# NullPool engine here; get_session_factory() prefers it when present.
_worker_session_factory: contextvars.ContextVar = contextvars.ContextVar(
    "worker_session_factory", default=None
)


def create_worker_engine_and_factory() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """A fresh engine bound to the current event loop. NullPool means no
    connection is cached/reused across loops — safe for one-shot worker tasks."""
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession,
        expire_on_commit=False, autocommit=False, autoflush=False,
    )
    return engine, factory


def set_worker_session_factory(factory: async_sessionmaker[AsyncSession] | None) -> None:
    _worker_session_factory.set(factory)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    # Worker tasks set a per-run factory bound to their own loop.
    worker_factory = _worker_session_factory.get()
    if worker_factory is not None:
        return worker_factory

    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


# Alias for convenience (used by WebSocket endpoint)
AsyncSessionLocal = get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database engine on startup."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        logger.info("Database connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


async def close_db() -> None:
    """Dispose of the database engine on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed")
