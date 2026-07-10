"""models/product.py — Product catalog table."""
from sqlalchemy import Float, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Product(Base):
    """A single catalog item, seeded from the Shwapno scrape."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name_bn: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # Numeric for DB-level fixed-precision money storage; asdecimal=False keeps
    # the Python-side value a plain float, since agent/matcher.py and
    # agent/pipeline.py already do float arithmetic on this field.
    price_bdt: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    unit_value: Mapped[float] = mapped_column(Float, nullable=False)
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Embedding vector for name_en, used only by the optional Layer 1
    # embedding-retrieval addition in agent/embedding_match.py (see
    # ENABLE_EMBEDDING_MATCH in core/config.py). Plain JSON list of floats,
    # not a native pgvector `vector` column: that type is Postgres-only and
    # would break this project's SQLite-local/Postgres-prod parity. Null
    # until seed/embed_products.py backfills it.
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    # Which embedding model actually produced `embedding` — rotation
    # (core/gemini_client.py) can fall back from EMBEDDING_MODEL to
    # EMBEDDING_MODEL_FALLBACK mid-backfill (or mid-session, for a query
    # embedding), and two models' vectors aren't guaranteed comparable even
    # at the same dimension. agent/embedding_match.py only ever compares a
    # query embedding against product embeddings tagged with this same
    # value, never across models.
    embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
