"""models/embedding_cache.py — Persistent cache for query-time ingredient
embeddings (see core/embeddings.py), so a repeated ingredient phrasing
never re-hits the Gemini embedding API even across a redeploy.

Was a local SQLite file (embedding_cache.db) — moved into the same
database as everything else (Postgres in prod / SQLite locally, same
DATABASE_URL) since a local file doesn't survive Render's free tier
redeploys (no persistent disk configured), unlike this table."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class EmbeddingCacheEntry(Base):
    __tablename__ = "embedding_cache"

    # sha256(text) — see core/embeddings.py's _cache_key(). Not model-scoped
    # on purpose: a cache hit returns whichever model embedded it
    # originally, no API call needed regardless of which model is
    # reachable right now.
    key: Mapped[str] = mapped_column(String, primary_key=True)
    vector: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
