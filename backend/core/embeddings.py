"""
core/embeddings.py — Gemini embedding-vector wrapper.

Same shape as core/llm.py: a thin, provider-specific wrapper plus a local
SQLite cache, so callers never touch the SDK directly and never pay twice
for an identical text. Used only by the Layer 1 retrieval addition in
agent/embedding_match.py — nothing else in this codebase calls it, and it's
inert unless ENABLE_EMBEDDING_MATCH=true (see core/config.py).
"""
import asyncio
import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path

from core.config import GOOGLE_API_KEY, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_CACHE_DB_PATH = Path(__file__).resolve().parent.parent / "embedding_cache.db"


def _cache_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_CACHE_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS embedding_cache "
        "(key TEXT PRIMARY KEY, vector TEXT, created_at TEXT)"
    )
    return conn


def _cache_key(text: str, model: str) -> str:
    return hashlib.sha256(f"{model}:{text}".encode("utf-8")).hexdigest()


def _cache_get_many(keys: list[str]) -> dict[str, list[float]]:
    if not keys:
        return {}
    conn = _cache_conn()
    try:
        placeholders = ",".join("?" for _ in keys)
        rows = conn.execute(
            f"SELECT key, vector FROM embedding_cache WHERE key IN ({placeholders})", keys
        ).fetchall()
        return {key: json.loads(vector) for key, vector in rows}
    finally:
        conn.close()


def _cache_set_many(items: dict[str, list[float]]) -> None:
    if not items:
        return
    conn = _cache_conn()
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO embedding_cache (key, vector, created_at) VALUES (?, ?, ?)",
            [(key, json.dumps(vec), time.strftime("%Y-%m-%d %H:%M:%S")) for key, vec in items.items()],
        )
        conn.commit()
    finally:
        conn.close()


def embed_texts(texts: list[str], use_cache: bool = True) -> list[list[float]]:
    """Returns one embedding vector per input text, in order.

    Cache is keyed per-text (not per-batch), so a repeated ingredient
    phrasing across different chat messages never re-hits the API even if
    it's batched alongside different texts each time.
    """
    if not texts:
        return []

    keys = [_cache_key(t, EMBEDDING_MODEL) for t in texts]
    cached = _cache_get_many(keys) if use_cache else {}

    missing_idx = [i for i, k in enumerate(keys) if k not in cached]
    if missing_idx:
        fresh = _gemini_embed([texts[i] for i in missing_idx])
        new_entries = {keys[i]: vec for i, vec in zip(missing_idx, fresh)}
        cached.update(new_entries)
        if use_cache:
            _cache_set_many(new_entries)

    return [cached[k] for k in keys]


async def aembed_texts(texts: list[str], use_cache: bool = True) -> list[list[float]]:
    """Async wrapper — offloads the blocking API call so the FastAPI event
    loop is never blocked by embedding latency (same pattern as llm.achat)."""
    return await asyncio.to_thread(embed_texts, texts, use_cache)


def _gemini_embed(texts: list[str]) -> list[list[float]]:
    from google import genai
    from google.genai import errors as genai_errors

    client = genai.Client(api_key=GOOGLE_API_KEY)

    for attempt in range(3):
        try:
            response = client.models.embed_content(model=EMBEDDING_MODEL, contents=texts)
            return [e.values for e in response.embeddings]
        except genai_errors.ClientError as e:
            if e.code == 429 or e.status == "RESOURCE_EXHAUSTED":
                wait = 20 * (attempt + 1)
                logger.warning(f"[embeddings] Gemini rate-limited, retrying in {wait}s: {e}")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("Gemini embedding API rate-limited after 3 retries")
