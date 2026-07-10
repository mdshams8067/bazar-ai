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
    SECRET_KEY: str = "dev-only-insecure-secret-override-in-.env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days — a demo, not a bank
    ENV: str = "local"
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
    GOOGLE_API_KEY: str = ""
    GEMINI_TEXT_MODEL: str = "gemini-3.1-flash-lite"

    # ── Groq ──────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_TEXT_MODEL: str = "qwen/qwen3-32b"

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
CORS_ORIGINS = settings.CORS_ORIGINS
LLM_PROVIDER = settings.LLM_PROVIDER
LLM_FALLBACK_PROVIDER = settings.LLM_FALLBACK_PROVIDER
GOOGLE_API_KEY = settings.GOOGLE_API_KEY
GEMINI_TEXT_MODEL = settings.GEMINI_TEXT_MODEL
GROQ_API_KEY = settings.GROQ_API_KEY
GROQ_TEXT_MODEL = settings.GROQ_TEXT_MODEL
SSLCOMMERZ_STORE_ID = settings.SSLCOMMERZ_STORE_ID
SSLCOMMERZ_STORE_PASSWORD = settings.SSLCOMMERZ_STORE_PASSWORD
SSLCOMMERZ_API_URL = settings.SSLCOMMERZ_API_URL
SSLCOMMERZ_VALIDATION_URL = settings.SSLCOMMERZ_VALIDATION_URL
BACKEND_URL = settings.BACKEND_URL
FRONTEND_URL = settings.FRONTEND_URL
