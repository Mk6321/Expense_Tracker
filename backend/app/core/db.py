from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# pgbouncer (transaction mode) cannot use server-side prepared statements, and the
# Supabase free tier has a small connection cap -- hence the tiny pool.
_engine_kwargs: dict = {"echo": settings.DB_ECHO, "pool_pre_ping": True}
if not _is_sqlite:
    _engine_kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

SessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """One session per request. Routes/services share it so a whole request's
    financial writes commit or roll back together (§4)."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
