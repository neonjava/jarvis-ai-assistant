"""
Async Database Engine + Session Management
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from loguru import logger

from config.settings import settings
from database.models import Base

# ── Engine ────────────────────────────────────────────────────────────────────

def _create_engine() -> AsyncEngine:
    url = settings.DATABASE_URL
    kwargs: dict = {}

    if "sqlite" in url:
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["echo"] = settings.DEBUG
    else:
        # PostgreSQL
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_pre_ping"] = True
        kwargs["echo"] = settings.DEBUG

    return create_async_engine(url, **kwargs)


engine: AsyncEngine = _create_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Session dependency ────────────────────────────────────────────────────────

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a DB session."""
    async with get_db_session() as session:
        yield session


# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables initialized")


async def close_db() -> None:
    """Dispose engine on shutdown."""
    await engine.dispose()
    logger.info("Database connection closed")
