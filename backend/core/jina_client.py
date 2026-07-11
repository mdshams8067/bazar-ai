"""
core/jina_client.py — Jina AI embeddings + reranking, called via plain REST
(no SDK — see core/config.py's JINA_API_KEY comment for why: the official
`voyageai` SDK pulled in LangChain as a transitive dependency when that
provider was tried first, and this project deliberately doesn't use
LangChain, so every provider in this project talks to its REST API
directly instead of trusting an SDK's dependency tree).

Self-paces to JINA_REQUESTS_PER_MINUTE rather than firing requests blindly
and retrying into 429s — verified live that the free tier is a hard cap
enforced per-minute, not a soft "burst then throttle" limit.
"""
import logging
import threading
import time

import requests

from core.config import JINA_API_KEY, JINA_EMBEDDING_MODEL, JINA_RERANK_MODEL, JINA_REQUESTS_PER_MINUTE

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.jina.ai/v1"
_MIN_INTERVAL = 60.0 / max(JINA_REQUESTS_PER_MINUTE, 1)

_pace_lock = threading.Lock()
_last_request_at = 0.0


def _pace() -> None:
    """Blocks just long enough to keep this process under
    JINA_REQUESTS_PER_MINUTE, shared across every call site in this
    module (embed and rerank draw from the same per-key rate limit)."""
    global _last_request_at
    with _pace_lock:
        wait = _last_request_at + _MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def _post(path: str, payload: dict) -> dict:
    for attempt in range(3):
        _pace()
        response = requests.post(
            f"{_BASE_URL}/{path}",
            headers={"Authorization": f"Bearer {JINA_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if response.status_code == 200:
            return response.json()
        if response.status_code == 429:
            wait = 15 * (attempt + 1)
            logger.warning(f"[jina] rate-limited on {path}, retrying in {wait}s: {response.text[:200]}")
            time.sleep(wait)
            continue
        response.raise_for_status()
    raise RuntimeError(f"Jina {path} rate-limited after 3 retries")


def embed_texts(texts: list[str], model: str = JINA_EMBEDDING_MODEL) -> list[list[float]]:
    """Returns one embedding vector per input text, in order. No caching
    here — core/embeddings.py's cache layer (shared across providers)
    already handles that."""
    if not texts:
        return []
    data = _post("embeddings", {"input": texts, "model": model})
    return [row["embedding"] for row in data["data"]]


def rerank(query: str, documents: list[str], model: str = JINA_RERANK_MODEL) -> list[tuple[int, float]]:
    """Scores every document's relevance to query. Returns (original_index,
    relevance_score) pairs, sorted best-first. Deliberately returns the
    *index* into the original `documents` list rather than the document
    text itself — agent/embedding_match.py needs to map results back to
    real Product rows, not re-match on text."""
    if not documents:
        return []
    data = _post("rerank", {"query": query, "documents": documents, "model": model})
    results = [(row["index"], row["relevance_score"]) for row in data["results"]]
    results.sort(key=lambda pair: pair[1], reverse=True)
    return results
