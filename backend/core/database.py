"""
core/database.py — SQLAlchemy async engine/session setup.

DATABASE_URL (the single source of truth from .env / hosting env) is given
in its plain form — e.g. sqlite:///bazar.db locally, or the plain
postgresql://... string Render/Railway/Supabase hand you. This module
derives the async-driver variant (sqlite+aiosqlite / postgresql+asyncpg)
for the app's engine, so no extra env var or manual driver suffix is
needed. seed/seed_db.py deliberately uses its own separate sync engine —
seeding is a one-off script, not part of the request path, so there's no
benefit to async ceremony there.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import DATABASE_URL


def _to_async_url(url: str) -> str:
    """Adds the async driver to a plain sync-style DATABASE_URL."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_async_engine(_to_async_url(DATABASE_URL), connect_args=_connect_args)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a request-scoped async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
