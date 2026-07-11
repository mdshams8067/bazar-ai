"""
core/embeddings.py — Provider-agnostic embedding-vector wrapper.

Same shape as core/llm.py: a thin, provider-abstracted wrapper plus a
cache, so callers never touch a provider's API directly and never pay
twice for an identical text. Jina is the primary provider (EMBEDDING_
PROVIDER, default "jina"), Gemini the coded fallback (EMBEDDING_FALLBACK_
PROVIDER) if Jina's key/quota is ever unavailable — same primary/fallback
shape core/llm.py already uses for Gemini/Groq. Used only by the Layer 1
retrieval addition in agent/embedding_match.py — nothing else in this
codebase calls it, and it's inert unless ENABLE_EMBEDDING_MATCH=true (see
core/config.py).

The cache lives in the same database as everything else (models/
embedding_cache.py, Postgres in prod / SQLite locally via the usual
DATABASE_URL swap) rather than a local SQLite file — a local file doesn't
survive Render's free-tier redeploys (no persistent disk configured), so
every restart was silently re-paying for embeddings it already had. Uses
its own plain sync engine, same deliberate exception as seed/seed_db.py:
embed_texts() is itself a sync function run inside asyncio.to_thread (see
aembed_texts below), so a sync DB call here never blocks the event loop —
there's no benefit to async ceremony in a function that's already off the
main thread.

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
import logging
import time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from core.config import (
    DATABASE_URL,
    EMBEDDING_FALLBACK_PROVIDER,
    EMBEDDING_MODEL,
    EMBEDDING_MODEL_FALLBACK,
    EMBEDDING_PROVIDER,
    JINA_EMBEDDING_MODEL,
)
from core.gemini_client import GeminiAllKeysExhausted, RotatableModelError, call_with_rotation
from models.embedding_cache import EmbeddingCacheEntry

logger = logging.getLogger(__name__)

_sync_engine = create_engine(DATABASE_URL)
_SyncSession = sessionmaker(bind=_sync_engine)


def _cache_key(text: str) -> str:
    # Not model-scoped on purpose: a cache hit means "we already have *an*
    # embedding for this text" and returns whichever model produced it
    # alongside the vector — no API call needed regardless of whether that
    # model is reachable right now. See module docstring for why the model
    # travels everywhere with its vector.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_get_many(db: Session, keys: list[str]) -> dict[str, tuple[list[float], str]]:
    if not keys:
        return {}
    rows = db.execute(select(EmbeddingCacheEntry).where(EmbeddingCacheEntry.key.in_(keys))).scalars().all()
    return {row.key: (row.vector, row.model) for row in rows}


def _cache_set_many(db: Session, items: dict[str, tuple[list[float], str]]) -> None:
    if not items:
        return
    # merge(), not add(): a rare race between two concurrent requests
    # embedding the same never-before-seen text would otherwise hit a
    # primary-key collision on insert — merge() upserts instead, portable
    # across SQLite and Postgres without dialect-specific ON CONFLICT SQL.
    for key, (vector, model) in items.items():
        db.merge(EmbeddingCacheEntry(key=key, vector=vector, model=model))
    db.commit()


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
    db = _SyncSession()
    try:
        cached = _cache_get_many(db, keys) if use_cache else {}

        missing_idx = [i for i, k in enumerate(keys) if k not in cached]
        if missing_idx:
            fresh_vectors, model_used = _dispatch_embed([texts[i] for i in missing_idx])
            new_entries = {keys[i]: (vec, model_used) for i, vec in zip(missing_idx, fresh_vectors)}
            cached.update(new_entries)
            if use_cache:
                _cache_set_many(db, new_entries)

        return [cached[k] for k in keys]
    finally:
        db.close()


async def aembed_texts(texts: list[str], use_cache: bool = True) -> list[tuple[list[float], str]]:
    """Async wrapper — offloads the blocking API call (and the sync DB
    cache lookup alongside it) so the FastAPI event loop is never blocked
    (same pattern as llm.achat)."""
    return await asyncio.to_thread(embed_texts, texts, use_cache)


def _dispatch_embed(texts: list[str]) -> tuple[list[list[float]], str]:
    """Tries EMBEDDING_PROVIDER first, falls over to EMBEDDING_FALLBACK_
    PROVIDER only if the primary raises — same primary/fallback shape
    core/llm.py already uses for Gemini/Groq, just for embeddings."""
    providers = [EMBEDDING_PROVIDER]
    if EMBEDDING_FALLBACK_PROVIDER and EMBEDDING_FALLBACK_PROVIDER != EMBEDDING_PROVIDER:
        providers.append(EMBEDDING_FALLBACK_PROVIDER)

    last_error: Exception | None = None
    for provider in providers:
        try:
            if provider == "jina":
                return _jina_embed(texts)
            return _gemini_embed(texts)
        except Exception as e:
            logger.warning(f"[embeddings] provider={provider} failed, trying next: {e}")
            last_error = e
            continue

    raise RuntimeError(f"All embedding providers exhausted: {providers}") from last_error


def _jina_embed(texts: list[str]) -> tuple[list[list[float]], str]:
    """No key rotation (only one Jina key configured) — Jina's own client
    (core/jina_client.py) already retries transient rate limits with
    backoff; a failure that survives those retries propagates here and
    triggers the Gemini fallback above instead."""
    from core.jina_client import embed_texts as jina_embed

    vectors = jina_embed(texts, model=JINA_EMBEDDING_MODEL)
    return vectors, JINA_EMBEDDING_MODEL


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
        result = [e.values for e in response.embeddings]
        if len(result) != len(texts):
            # Doesn't raise on an oversized batch — verified live that
            # gemini-embedding-2 silently returns exactly 1 embedding
            # regardless of how many texts are sent (2 in -> 1 out, 50 in
            # -> 1 out). Treated as "this model can't serve this request"
            # rather than trusted, since zipping a short result against the
            # full input list would otherwise silently mismap vectors to
            # the wrong text/product instead of failing loudly.
            raise RotatableModelError(
                f"model={model} returned {len(result)} embeddings for {len(texts)} inputs"
            )
        return result

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
