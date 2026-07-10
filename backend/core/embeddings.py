"""
core/embeddings.py — Gemini embedding-vector wrapper.

Same shape as core/llm.py: a thin, provider-specific wrapper plus a local
SQLite cache, so callers never touch the SDK directly and never pay twice
for an identical text. Used only by the Layer 1 retrieval addition in
agent/embedding_match.py — nothing else in this codebase calls it, and it's
inert unless ENABLE_EMBEDDING_MATCH=true (see core/config.py).

Every embedding is returned/stored alongside the model that produced it
(core/gemini_client.py may rotate from EMBEDDING_MODEL to
EMBEDDING_MODEL_FALLBACK, or across API keys, mid-session) — two vectors
from different embedding models aren't guaranteed to live in a comparable
space even if their dimensions happen to match, so nothing downstream may
ever compare vectors from different models. See agent/embedding_match.py,
which only compares a query embedding against product embeddings tagged
with that same model.
"""
import asyncio
import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path

from core.config import EMBEDDING_MODEL, EMBEDDING_MODEL_FALLBACK
from core.gemini_client import GeminiAllKeysExhausted, call_with_rotation

logger = logging.getLogger(__name__)

_CACHE_DB_PATH = Path(__file__).resolve().parent.parent / "embedding_cache.db"


def _cache_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_CACHE_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS embedding_cache "
        "(key TEXT PRIMARY KEY, vector TEXT, model TEXT, created_at TEXT)"
    )
    # Self-heal a cache file created before the `model` column existed
    # (CREATE TABLE IF NOT EXISTS doesn't alter an already-existing table) —
    # this cache is local, disposable, and rebuilds itself from scratch
    # either way, but crashing every embed call on a stale schema instead
    # of just adding the column is a needless failure mode.
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(embedding_cache)")}
    if "model" not in existing_columns:
        conn.execute("ALTER TABLE embedding_cache ADD COLUMN model TEXT")
    return conn


def _cache_key(text: str) -> str:
    # Not model-scoped on purpose: a cache hit means "we already have *an*
    # embedding for this text" and returns whichever model produced it
    # alongside the vector — no API call needed regardless of whether that
    # model is reachable right now. See module docstring for why the model
    # travels everywhere with its vector.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_get_many(keys: list[str]) -> dict[str, tuple[list[float], str]]:
    if not keys:
        return {}
    conn = _cache_conn()
    try:
        placeholders = ",".join("?" for _ in keys)
        rows = conn.execute(
            f"SELECT key, vector, model FROM embedding_cache WHERE key IN ({placeholders})", keys
        ).fetchall()
        return {key: (json.loads(vector), model) for key, vector, model in rows}
    finally:
        conn.close()


def _cache_set_many(items: dict[str, tuple[list[float], str]]) -> None:
    if not items:
        return
    conn = _cache_conn()
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO embedding_cache (key, vector, model, created_at) VALUES (?, ?, ?, ?)",
            [
                (key, json.dumps(vec), model, time.strftime("%Y-%m-%d %H:%M:%S"))
                for key, (vec, model) in items.items()
            ],
        )
        conn.commit()
    finally:
        conn.close()


def embed_texts(texts: list[str], use_cache: bool = True) -> list[tuple[list[float], str]]:
    """Returns one (vector, model_used) pair per input text, in order.

    Cache is keyed per-text (not per-batch), so a repeated ingredient
    phrasing across different chat messages never re-hits the API even if
    it's batched alongside different texts each time. Different texts in
    one call can legitimately come back tagged with different models — a
    cache hit returns whatever model embedded it originally; a fresh call
    returns whatever model rotation actually landed on this time — so
    callers must key any per-item bookkeeping (e.g. Product.embedding_model)
    off the model each item actually reports, not assume one model per call.
    """
    if not texts:
        return []

    keys = [_cache_key(t) for t in texts]
    cached = _cache_get_many(keys) if use_cache else {}

    missing_idx = [i for i, k in enumerate(keys) if k not in cached]
    if missing_idx:
        fresh_vectors, model_used = _gemini_embed([texts[i] for i in missing_idx])
        new_entries = {keys[i]: (vec, model_used) for i, vec in zip(missing_idx, fresh_vectors)}
        cached.update(new_entries)
        if use_cache:
            _cache_set_many(new_entries)

    return [cached[k] for k in keys]


async def aembed_texts(texts: list[str], use_cache: bool = True) -> list[tuple[list[float], str]]:
    """Async wrapper — offloads the blocking API call so the FastAPI event
    loop is never blocked by embedding latency (same pattern as llm.achat)."""
    return await asyncio.to_thread(embed_texts, texts, use_cache)


def _gemini_embed(texts: list[str]) -> tuple[list[list[float]], str]:
    """One batch, one model: rotation tries EMBEDDING_MODEL then
    EMBEDDING_MODEL_FALLBACK on the same key before moving to the next key
    (see core/gemini_client.py) — whichever (key, model) combo actually
    succeeds serves the *whole* batch, so every text in this call comes
    back tagged with the same model_used."""
    from google import genai

    def _make_call(api_key: str, model: str) -> list[list[float]]:
        client = genai.Client(api_key=api_key)
        response = client.models.embed_content(model=model, contents=texts)
        return [e.values for e in response.embeddings]

    try:
        vectors, model_used = call_with_rotation(
            _make_call, models=[EMBEDDING_MODEL, EMBEDDING_MODEL_FALLBACK]
        )
        return vectors, model_used
    except GeminiAllKeysExhausted:
        # Nowhere left to rotate to (no fallback provider exists for
        # embeddings, unlike core/llm.py's Groq) — wait out a likely
        # transient burst and try the full rotation again, a few times,
        # before giving up for good.
        for attempt in range(2):
            wait = 30 * (attempt + 1)
            logger.warning(f"[embeddings] all keys/models exhausted, retrying full rotation in {wait}s")
            time.sleep(wait)
            try:
                vectors, model_used = call_with_rotation(
                    _make_call, models=[EMBEDDING_MODEL, EMBEDDING_MODEL_FALLBACK]
                )
                return vectors, model_used
            except GeminiAllKeysExhausted:
                continue
        raise RuntimeError("Gemini embedding API: all keys/models exhausted after retries")
