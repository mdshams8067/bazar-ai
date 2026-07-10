"""
core/gemini_client.py — Shared Gemini API-key (and, for embeddings,
fallback-model) rotation, used by both core/llm.py (chat) and
core/embeddings.py (embeddings) — one shared pool of keys, since both draw
on the same Gemini account/quota, and both have hit real, live rate limits
this project (see PROJECT_CONTEXT.md).

Rotation order: for a single key, try every model in `models` first (a
different model on the SAME key has its own quota bucket — a free extra
attempt before burning a key switch); only once every model is exhausted
on that key does this move to the next key and try the same model list
again there. Only rate-limit-shaped errors (429/RESOURCE_EXHAUSTED) or an
invalid/revoked key (401/403) trigger rotation — anything else (a genuine
bad request, a real server error) propagates immediately, since rotating
keys/models can't fix those and silently retrying would just hide a real
bug.
"""
import logging
from typing import Callable, TypeVar

from google.genai import errors as genai_errors

from core.config import GEMINI_API_KEYS

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GeminiAllKeysExhausted(Exception):
    """Every configured API key, and every model tried per key, was
    rate-limited (or the key itself was rejected) — nowhere left to
    rotate to."""


def _error_reason(e: genai_errors.ClientError) -> str | None:
    """The specific machine-readable reason nested inside the API's error
    body (e.g. "API_KEY_INVALID", "API_KEY_SERVICE_BLOCKED") — `.status`
    alone is too coarse for this (an invalid key comes back as a bare
    `400 INVALID_ARGUMENT`, the same top-level status a genuinely malformed
    request — e.g. a typo'd model name — would also get, and those must
    NOT trigger rotation, since a different key can't fix a bad request)."""
    try:
        details = e.details.get("error", {}) if isinstance(e.details, dict) else {}
        for detail in details.get("details", []):
            if str(detail.get("@type", "")).endswith("ErrorInfo"):
                return detail.get("reason")
    except AttributeError:
        pass
    return None


def _is_rotatable(e: Exception) -> bool:
    """Rate-limited, this specific key is bad, or this specific model is
    unavailable (deprecated, not found, no access) — all three mean "this
    (key, model) combo won't work, try the next one in the loop," as
    opposed to a genuine malformed-payload error that would fail
    identically on every (key, model) pair and must propagate instead of
    silently burning through the whole rotation list.

    The model-unavailable case is real, not hypothetical: verified live
    that `gemini-2.5-flash` and `gemini-2.5-flash-lite` both now 404 with
    "no longer available to new users" — a fallback model list will
    inevitably go stale as Google deprecates models over time, and a
    single stale entry should be skipped, not take down the whole chat
    turn. Since call_with_rotation already tries every model before
    switching keys, treating 404 as rotatable naturally lands on the next
    model on the same key first, exactly as intended."""
    if not isinstance(e, genai_errors.ClientError):
        return False
    code = getattr(e, "code", None)
    status = getattr(e, "status", None)
    if code == 429 or status == "RESOURCE_EXHAUSTED":
        return True
    if code in (401, 403) or status in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
        return True
    if code == 404 or status == "NOT_FOUND":
        return True
    reason = _error_reason(e)
    return bool(reason) and reason.startswith("API_KEY_")


def call_with_rotation(make_call: Callable[[str, str], T], models: list[str]) -> tuple[T, str]:
    """Tries every (api_key, model) pair — models innermost, keys outermost
    (see module docstring for why). `make_call(api_key, model)` performs
    one real request and should let a rotatable error propagate rather
    than swallow it, so this loop can react; any other exception
    propagates immediately, uncaught.

    Returns (result, model_used) — callers that need to know which model
    actually served the request (core/embeddings.py, so it can record
    which embedding space a vector belongs to) use the second element;
    callers that don't (core/llm.py, one model only) can ignore it."""
    if not GEMINI_API_KEYS:
        raise RuntimeError("No Gemini API key configured (GOOGLE_API_KEY / GOOGLE_API_KEYS_EXTRA)")

    last_error: Exception | None = None
    for key_index, api_key in enumerate(GEMINI_API_KEYS):
        for model in models:
            try:
                return make_call(api_key, model), model
            except genai_errors.ClientError as e:
                if not _is_rotatable(e):
                    raise
                logger.warning(
                    f"[gemini] key#{key_index + 1}/{len(GEMINI_API_KEYS)} model={model} "
                    f"unavailable, rotating: {e}"
                )
                last_error = e
                continue

    raise GeminiAllKeysExhausted(
        f"All {len(GEMINI_API_KEYS)} Gemini API key(s) x {len(models)} model(s) exhausted"
    ) from last_error
