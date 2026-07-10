"""
seed/embed_products.py — One-off backfill: computes and stores an embedding
vector for every product's name_en, for the optional Layer 1
embedding-retrieval addition (see ENABLE_EMBEDDING_MATCH in core/config.py
and agent/embedding_match.py).

Only needs to be (re-)run when the catalog changes — after seed.seed_db, or
whenever new products are added. Safe to re-run any time: by default only
fills in products with no embedding yet (see backfill()'s only_missing
param), so re-running after a partial run (e.g. a quota wall — see
PROJECT_CONTEXT.md) or on a growing catalog never wastes quota re-embedding
what already succeeded.

Run as a script: `python -m seed.embed_products` from backend/ (venv active).
"""
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import DATABASE_URL
from core.embeddings import embed_texts
from models.product import Product

logger = logging.getLogger(__name__)

# Gemini's embed_content accepts a batch per call, but very large batches
# risk hitting per-request payload/rate limits — chunking keeps each call
# small and keeps a partial failure from losing all prior progress.
_BATCH_SIZE = 100

_sync_engine = create_engine(DATABASE_URL)
_SyncSession = sessionmaker(bind=_sync_engine)


def backfill(only_missing: bool = True) -> int:
    """Embeds and stores name_en for every product. Returns row count updated.

    only_missing=True (default) skips products that already have an
    embedding — safe to re-run after a partial run (e.g. hitting the
    embedding API's free-tier daily quota partway through a large catalog)
    without wasting quota re-embedding what already succeeded. Pass False
    to force a full re-embed (e.g. after switching EMBEDDING_MODEL)."""
    db = _SyncSession()
    try:
        query = db.query(Product).order_by(Product.id)
        if only_missing:
            query = query.filter(Product.embedding.is_(None))
        products = query.all()
        for start in range(0, len(products), _BATCH_SIZE):
            batch = products[start : start + _BATCH_SIZE]
            vectors = embed_texts([p.name_en for p in batch])
            for product, vector in zip(batch, vectors):
                product.embedding = vector
            db.commit()
            logger.info(f"Embedded {start + len(batch)}/{len(products)} products")
    finally:
        db.close()

    return len(products)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = backfill()
    print(f"Backfilled embeddings for {count} products into {_sync_engine.url}")
