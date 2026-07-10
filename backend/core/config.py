"""
core/config.py — Central settings, loaded from the environment / .env via
pydantic-settings.

Module-level constants (DATABASE_URL, GOOGLE_API_KEY, ...) are kept for
backward compatibility with modules that already import them directly
(core/llm.py, core/database.py, seed/seed_db.py) — they're just aliases for
`settings.<FIELD>`, so there is exactly one source of truth.
"""
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
_DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent.parent / "bazar.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = f"sqlite:///{_DEFAULT_SQLITE_PATH}"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _default_database_url(cls, v: object) -> object:
        """An empty string in .env (DATABASE_URL=) is a real value to
        pydantic, not "unset" — treat it the same as unset so local dev
        falls back to SQLite."""
        if not v or not str(v).strip():
            return f"sqlite:///{_DEFAULT_SQLITE_PATH}"
        return v

    # ── Auth / CORS ───────────────────────────────────────────────────────
    # SECRET_KEY/ACCESS_TOKEN_EXPIRE_MINUTES are vestigial — this backend no
    # longer issues its own tokens (Supabase does), kept only so an existing
    # .env with these set doesn't error on the unrelated `extra="ignore"`
    # config above being any stricter than it needs to be.
    SECRET_KEY: str = "dev-only-insecure-secret-override-in-.env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ENV: str = "local"
    # Supabase project URL — used to fetch their public JWKS for verifying
    # tokens the frontend obtains directly from Supabase's own Auth API.
    SUPABASE_URL: str = ""
    # NoDecode: skip pydantic-settings' default JSON-decode attempt for env
    # values so a plain comma-separated string (the easy thing to type in
    # .env) reaches the validator below untouched.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, v: object) -> object:
        """Accepts either a comma-separated string (easiest to type in
        .env) or an already-parsed list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── LLM provider selection ────────────────────────────────────────────
    LLM_PROVIDER: str = "gemini"
    LLM_FALLBACK_PROVIDER: str = "groq"

    # ── Gemini ────────────────────────────────────────────────────────────
    # Primary key, kept as a single scalar for backward compatibility with
    # every existing .env. Additional keys (optional) go in
    # GOOGLE_API_KEYS_EXTRA, comma-separated — see GEMINI_API_KEYS below,
    # the actual combined list core/gemini_client.py rotates through when
    # one key gets rate-limited (a free-tier key's quota, per-key and
    # per-model, is a real thing this project has hit live — see
    # PROJECT_CONTEXT.md). Used by both the chat LLM (core/llm.py) and the
    # embedding matcher addition (core/embeddings.py) — one shared pool of
    # keys, since both draw from the same Gemini account/quota.
    GOOGLE_API_KEY: str = ""
    GOOGLE_API_KEYS_EXTRA: Annotated[list[str], NoDecode] = []
    GEMINI_TEXT_MODEL: str = "gemini-3.1-flash-lite"
    # Tried, same key, before rotating to the next key — same reasoning as
    # EMBEDDING_MODEL_FALLBACK below. Defaults are real models confirmed
    # working against this project's own Gemini account (verified live,
    # not guessed from a model-name list): gemini-flash-lite-latest is an
    # auto-updating alias close to the primary's own tier, the other two
    # are a genuinely different model generation/tier as a further
    # backstop. A few plausible-looking candidates were tried and rejected
    # live: gemini-2.5-flash/-flash-lite are deprecated for new API keys
    # ("no longer available to new users"), gemini-2.0-flash/-flash-lite
    # and gemini-3.1-pro-preview returned 429s immediately (zero granted
    # quota on this account's tier, not a transient rate limit).
    GEMINI_TEXT_MODELS_FALLBACK: Annotated[list[str], NoDecode] = [
        "gemini-flash-lite-latest",
        "gemini-3-flash-preview",
        "gemini-3.5-flash",
    ]

    @field_validator(
        "GOOGLE_API_KEYS_EXTRA", "GEMINI_TEXT_MODELS_FALLBACK", "GROQ_TEXT_MODELS_FALLBACK", mode="before"
    )
    @classmethod
    def _split_comma_list(cls, v: object) -> object:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    # ── Matcher: embedding-based retrieval (Layer 1) ──────────────────────
    # When the exact/fuzzy keyword cascade in agent/matcher.py finds nothing,
    # optionally also try embedding similarity (a wider net for genuine
    # vocabulary mismatches, e.g. "chickpea flour" vs. a catalog product
    # named "Besan") before giving up. Purely additive — every downstream
    # decision (stock, price, substitution tiers) stays the same deterministic
    # code regardless of which tier found the candidate. Off by default so
    # this whole layer can be enabled/disabled with one env var, no revert
    # needed, if it ever needs to be pulled out.
    ENABLE_EMBEDDING_MATCH: bool = False
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    # Tried, same API key, before rotating to the next key (see
    # core/gemini_client.py) — a separate model on the same key has its own
    # quota bucket, so this is a free extra attempt before burning a key
    # switch. (The chat LLM's equivalent list is GEMINI_TEXT_MODELS_FALLBACK
    # above — kept separate since an embedding model and a chat model are
    # never interchangeable.)
    EMBEDDING_MODEL_FALLBACK: str = "gemini-embedding-2"

    # ── Groq ──────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_TEXT_MODEL: str = "qwen/qwen3-32b"
    # Same idea as GEMINI_TEXT_MODELS_FALLBACK, one provider over: tried in
    # order before giving up on Groq entirely (Groq is already the final
    # fallback after every Gemini key/model is exhausted — see
    # LLM_FALLBACK_PROVIDER below). Defaults verified working live against
    # this project's own Groq account. `openai/gpt-oss-20b` was tried and
    # excluded: it returned an empty string rather than an error or real
    # content, a silent-failure shape worse than not trying it at all.
    GROQ_TEXT_MODELS_FALLBACK: Annotated[list[str], NoDecode] = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "meta-llama/llama-4-scout-17b-16e-instruct",
    ]

    # ── SSLCommerz (payment gateway) ──────────────────────────────────────
    # Defaults are SSLCommerz's own publicly documented sandbox demo-store
    # credentials — not a placeholder, a real working test account. No
    # merchant registration is needed for sandbox use (only their live/
    # production gateway requires a registered business account). Override
    # in .env with your own sandbox or live credentials.
    SSLCOMMERZ_STORE_ID: str = "testbox"
    SSLCOMMERZ_STORE_PASSWORD: str = "qwerty"
    SSLCOMMERZ_API_URL: str = "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"
    SSLCOMMERZ_VALIDATION_URL: str = "https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php"
    # Used to build the success/fail/cancel/IPN callback URLs SSLCommerz
    # calls back on (must be reachable from SSLCommerz's servers, so this
    # needs to be a public URL in production, not localhost).
    BACKEND_URL: str = "http://localhost:8000"
    # Used to build the URL the customer's browser lands back on after
    # SSLCommerz finishes — the SPA, not this API.
    FRONTEND_URL: str = "http://localhost:5173"


settings = Settings()

DATABASE_URL = settings.DATABASE_URL
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
ENV = settings.ENV
SUPABASE_URL = settings.SUPABASE_URL
CORS_ORIGINS = settings.CORS_ORIGINS
LLM_PROVIDER = settings.LLM_PROVIDER
LLM_FALLBACK_PROVIDER = settings.LLM_FALLBACK_PROVIDER
GOOGLE_API_KEY = settings.GOOGLE_API_KEY
GOOGLE_API_KEYS_EXTRA = settings.GOOGLE_API_KEYS_EXTRA
GEMINI_TEXT_MODEL = settings.GEMINI_TEXT_MODEL
GEMINI_TEXT_MODELS_FALLBACK = settings.GEMINI_TEXT_MODELS_FALLBACK
# The actual list core/gemini_client.py rotates through: primary key first
# (so existing single-key setups are unaffected), then any extras,
# deduplicated in case the same key was pasted into both settings by
# mistake, blanks dropped.
GEMINI_API_KEYS = list(dict.fromkeys(k for k in [GOOGLE_API_KEY, *GOOGLE_API_KEYS_EXTRA] if k))
ENABLE_EMBEDDING_MATCH = settings.ENABLE_EMBEDDING_MATCH
EMBEDDING_MODEL = settings.EMBEDDING_MODEL
EMBEDDING_MODEL_FALLBACK = settings.EMBEDDING_MODEL_FALLBACK
GROQ_API_KEY = settings.GROQ_API_KEY
GROQ_TEXT_MODEL = settings.GROQ_TEXT_MODEL
GROQ_TEXT_MODELS_FALLBACK = settings.GROQ_TEXT_MODELS_FALLBACK
SSLCOMMERZ_STORE_ID = settings.SSLCOMMERZ_STORE_ID
SSLCOMMERZ_STORE_PASSWORD = settings.SSLCOMMERZ_STORE_PASSWORD
SSLCOMMERZ_API_URL = settings.SSLCOMMERZ_API_URL
SSLCOMMERZ_VALIDATION_URL = settings.SSLCOMMERZ_VALIDATION_URL
BACKEND_URL = settings.BACKEND_URL
FRONTEND_URL = settings.FRONTEND_URL
