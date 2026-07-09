"""
seed/seed_db.py — Load seed_data.json into the products table.

Uses its own plain synchronous engine, deliberately separate from the
app's async engine in core/database.py — seeding is a one-off CLI script,
not part of the request-serving path, so there's no benefit to async
ceremony here (see core/database.py's module docstring for the same call
made the other direction).

Run as a script: `python -m seed.seed_db` from backend/ (with venv active).
Idempotent: clears and re-inserts every run, so it's safe to re-seed after
schema changes during development.
"""
import json
import logging
from pathlib import Path

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from core.config import DATABASE_URL
from core.database import Base
from models.product import Product

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).resolve().parent / "seed_data.json"

_sync_engine = create_engine(DATABASE_URL)
_SyncSession = sessionmaker(bind=_sync_engine)


def seed() -> int:
    """Create tables (if needed) and load all products. Returns row count loaded."""
    Base.metadata.create_all(bind=_sync_engine)

    with open(SEED_FILE, encoding="utf-8") as f:
        rows = json.load(f)

    db = _SyncSession()
    try:
        db.query(Product).delete()
        db.bulk_save_objects([Product(**row) for row in rows])
        db.commit()

        # Sanity check: catch a silent data-loss transform bug (e.g. the
        # earlier bug that dropped fresh meat) immediately, not mid-demo.
        counts = dict(db.query(Product.category, func.count(Product.id)).group_by(Product.category).all())
        logger.info("Category counts: " + ", ".join(f"{cat}={n}" for cat, n in sorted(counts.items())))
        for cat in ("Meat", "Fish", "Rice"):
            if counts.get(cat, 0) == 0:
                raise AssertionError(f"Sanity check failed: category '{cat}' has 0 rows after seeding")
    finally:
        db.close()

    logger.info(f"Seeded {len(rows)} products from {SEED_FILE.name}")
    return len(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = seed()
    print(f"Seeded {count} products into {_sync_engine.url}")
