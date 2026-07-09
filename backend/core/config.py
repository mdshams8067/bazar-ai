"""
core/config.py — Central settings, loaded from the environment / .env via
pydantic-settings.

Module-level constants (GOOGLE_API_KEY, ...) are kept for backward
compatibility with modules that already import them directly (core/llm.py)
— they're just aliases for `settings.<FIELD>`, so there is exactly one
source of truth.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # ── LLM provider selection ────────────────────────────────────────────
    LLM_PROVIDER: str = "gemini"
    LLM_FALLBACK_PROVIDER: str = "groq"

    # ── Gemini ────────────────────────────────────────────────────────────
    GOOGLE_API_KEY: str = ""
    GEMINI_TEXT_MODEL: str = "gemini-3.1-flash-lite"

    # ── Groq ──────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_TEXT_MODEL: str = "qwen/qwen3-32b"


settings = Settings()

LLM_PROVIDER = settings.LLM_PROVIDER
LLM_FALLBACK_PROVIDER = settings.LLM_FALLBACK_PROVIDER
GOOGLE_API_KEY = settings.GOOGLE_API_KEY
GEMINI_TEXT_MODEL = settings.GEMINI_TEXT_MODEL
GROQ_API_KEY = settings.GROQ_API_KEY
GROQ_TEXT_MODEL = settings.GROQ_TEXT_MODEL
