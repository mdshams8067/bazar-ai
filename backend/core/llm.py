"""
core/llm.py — Provider-agnostic LLM wrapper.

Configure via .env:
  LLM_PROVIDER=gemini            (primary, default)
  LLM_FALLBACK_PROVIDER=groq     (used automatically if every Gemini key/model is rate-limited)

Within each provider, there's a second layer of fallback before ever
reaching the other provider: Gemini rotates across every key in
GOOGLE_API_KEY/GOOGLE_API_KEYS_EXTRA and every model in GEMINI_TEXT_MODEL +
GEMINI_TEXT_MODELS_FALLBACK (core/gemini_client.py); Groq rotates across
GROQ_TEXT_MODEL + GROQ_TEXT_MODELS_FALLBACK. Only once a provider's entire
key x model matrix is exhausted does this module fail over to the other
provider.

All agents call llm.chat() (or the async llm.achat()) — never the SDK directly.
Retry logic for transient 503 errors, and failover on 429 rate limits, lives
here so agents don't repeat it.

Response caching: identical (system_prompt, user_message, model) queries are
cached in a local SQLite table (llm_cache). Repeat dish queries — e.g. "morog
polao for 4" — produce identical ingredient JSON, so caching cuts free-tier
quota usage and gives instant responses for repeats.
"""
import asyncio
import hashlib
import logging
import re
import sqlite3
import time
from pathlib import Path

from core.config import (
    LLM_PROVIDER, LLM_FALLBACK_PROVIDER,
    GEMINI_TEXT_MODEL, GEMINI_TEXT_MODELS_FALLBACK,
    GROQ_API_KEY, GROQ_TEXT_MODEL, GROQ_TEXT_MODELS_FALLBACK,
)

logger = logging.getLogger(__name__)

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

_CACHE_DB_PATH = Path(__file__).resolve().parent.parent / "llm_cache.db"


class LLMUnavailableError(Exception):
    """Raised when the primary provider AND the fallback provider both fail."""


class _RateLimited(Exception):
    """Internal signal: this provider is rate-limited, try the next one."""


# ── Cache ─────────────────────────────────────────────────────────────────────

def _cache_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_CACHE_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS llm_cache "
        "(key TEXT PRIMARY KEY, response TEXT, created_at TEXT)"
    )
    return conn


def _cache_key(system: str, user: str, model: str) -> str:
    return hashlib.sha256(f"{system}{user}{model}".encode("utf-8")).hexdigest()


def _cache_get(key: str):
    conn = _cache_conn()
    try:
        row = conn.execute("SELECT response FROM llm_cache WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _cache_set(key: str, response: str) -> None:
    conn = _cache_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO llm_cache (key, response, created_at) VALUES (?, ?, ?)",
            (key, response, time.strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
    finally:
        conn.close()


# ── Public API ────────────────────────────────────────────────────────────────

def chat(system: str, user: str, max_tokens: int = 1024, temperature: float = 0.2,
         use_cache: bool = True) -> str:
    """Send a system + user prompt; return the model's text response.

    Tries LLM_PROVIDER first. If it hits a rate limit (HTTP 429) or otherwise
    exhausts its retries, fails over to LLM_FALLBACK_PROVIDER. Raises
    LLMUnavailableError only if both providers fail.
    """
    key = None
    if use_cache:
        model_for_key = GEMINI_TEXT_MODEL if LLM_PROVIDER == "gemini" else GROQ_TEXT_MODEL
        key = _cache_key(system, user, model_for_key)
        cached = _cache_get(key)
        if cached is not None:
            logger.info("[LLM] cache hit")
            return cached

    providers = [LLM_PROVIDER]
    if LLM_FALLBACK_PROVIDER and LLM_FALLBACK_PROVIDER != LLM_PROVIDER:
        providers.append(LLM_FALLBACK_PROVIDER)

    last_error = None
    for provider in providers:
        try:
            response = _dispatch(provider, system, user, max_tokens, temperature)
            if use_cache:
                _cache_set(key, response)
            return response
        except _RateLimited as e:
            logger.warning(f"[LLM] {provider} rate-limited, failing over: {e}")
            last_error = e
            continue

    raise LLMUnavailableError("All LLM providers are rate-limited or unavailable") from last_error


async def achat(system: str, user: str, max_tokens: int = 1024,
                 temperature: float = 0.2, use_cache: bool = True) -> str:
    """Async wrapper — offloads the blocking chat() to a thread so the
    FastAPI event loop is never blocked by LLM latency."""
    return await asyncio.to_thread(chat, system, user, max_tokens, temperature, use_cache)


def _dispatch(provider: str, system: str, user: str, max_tokens: int, temperature: float) -> str:
    if provider == "groq":
        return _groq_chat(system, user, max_tokens, temperature)
    return _gemini_chat(system, user, max_tokens, temperature)


# ── Gemini ────────────────────────────────────────────────────────────────────

def _gemini_chat(system: str, user: str, max_tokens: int, temperature: float) -> str:
    from google import genai
    from google.genai import types as genai_types
    from google.genai import errors as genai_errors

    from core.gemini_client import GeminiAllKeysExhausted, call_with_rotation

    def _make_call(api_key: str, model: str) -> str:
        client = genai.Client(api_key=api_key)

        def _call() -> str:
            response = client.models.generate_content(
                model=model,
                contents=user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                ),
            )
            return response.text.strip()

        # 503s are a Gemini service-health issue, not a quota one — retrying
        # a different key/model wouldn't help, so this stays a same-attempt
        # backoff retry rather than triggering rotation (genai_errors.
        # ServerError isn't a ClientError, so call_with_rotation never sees
        # it — it's handled here, same as before multi-key rotation existed).
        for attempt in range(3):
            try:
                return _call()
            except genai_errors.ServerError as e:
                wait = 30 * (attempt + 1)
                logger.warning(f"[LLM] Gemini 503, retrying in {wait}s: {e}")
                time.sleep(wait)
        raise RuntimeError("Gemini unavailable after 3 retries (503)")

    # Every model in GEMINI_TEXT_MODELS_FALLBACK is tried on each key before
    # rotating to the next key (see call_with_rotation's own docstring for
    # why that order). Once every key x model combination is exhausted,
    # this becomes a _RateLimited (this module's own signal), which
    # chat()'s caller already knows how to fail over from (Groq).
    try:
        result, _ = call_with_rotation(_make_call, models=[GEMINI_TEXT_MODEL, *GEMINI_TEXT_MODELS_FALLBACK])
        return result
    except GeminiAllKeysExhausted as e:
        raise _RateLimited(str(e)) from e


# ── Groq ──────────────────────────────────────────────────────────────────────

def _groq_chat(system: str, user: str, max_tokens: int, temperature: float) -> str:
    import groq
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)

    def _call(model: str) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = response.choices[0].message.content.strip()
        # Qwen3 models may prepend a <think>...</think> reasoning block.
        return _THINK_BLOCK_RE.sub("", text).strip()

    # Same rotation shape as Gemini's (core/gemini_client.py), just Groq's
    # own SDK exception types: try every model in order, moving on
    # immediately on a rate limit OR a "model not found" (groq.NotFoundError
    # — a fallback list will inevitably go stale as models get deprecated;
    # one bad entry should be skipped, not take down the whole chat turn);
    # a 500 gets a same-model backoff retry first (a real service blip, not
    # a quota/availability one) before also moving on to the next model
    # rather than giving up on Groq entirely.
    models = [GROQ_TEXT_MODEL, *GROQ_TEXT_MODELS_FALLBACK]
    last_error: Exception | None = None
    for model in models:
        try:
            for attempt in range(3):
                try:
                    return _call(model)
                except groq.InternalServerError as e:
                    wait = 30 * (attempt + 1)
                    logger.warning(f"[LLM] Groq 503 on {model}, retrying in {wait}s: {e}")
                    time.sleep(wait)
            logger.warning(f"[LLM] Groq {model} unavailable after 3 retries (503), trying next model")
        except groq.RateLimitError as e:
            logger.warning(f"[LLM] Groq {model} rate-limited, trying next model: {e}")
            last_error = e
            continue
        except groq.NotFoundError as e:
            logger.warning(f"[LLM] Groq {model} not found/no access, trying next model: {e}")
            last_error = e
            continue

    raise _RateLimited(str(last_error) if last_error else f"Groq: all {len(models)} model(s) exhausted (503)")
