"""
core/test_llm.py — Acceptance tests for the llm.py caching + failover behavior.

Provider SDK calls are monkeypatched at the _gemini_chat/_groq_chat boundary
so these tests run without real API keys or the `groq` package installed.
"""
import pytest

from core import llm


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "_CACHE_DB_PATH", tmp_path / "llm_cache.db")


def test_repeat_query_hits_cache(monkeypatch, caplog):
    calls = []

    def fake_gemini_chat(system, user, max_tokens, temperature):
        calls.append(1)
        return "ingredient json"

    monkeypatch.setattr(llm, "_gemini_chat", fake_gemini_chat)

    first = llm.chat("system prompt", "morog polao for 4")
    with caplog.at_level("INFO"):
        second = llm.chat("system prompt", "morog polao for 4")

    assert first == second == "ingredient json"
    assert len(calls) == 1  # provider only called once — second call was a cache hit
    assert "cache hit" in caplog.text


def test_failover_to_secondary_on_rate_limit(monkeypatch):
    def fake_gemini_chat(system, user, max_tokens, temperature):
        raise llm._RateLimited("gemini rate limited")

    def fake_groq_chat(system, user, max_tokens, temperature):
        return "fallback response"

    monkeypatch.setattr(llm, "_gemini_chat", fake_gemini_chat)
    monkeypatch.setattr(llm, "_groq_chat", fake_groq_chat)

    result = llm.chat("system prompt", "unique query one", use_cache=False)

    assert result == "fallback response"


def test_both_providers_failing_raises_llm_unavailable(monkeypatch):
    def fake_gemini_chat(system, user, max_tokens, temperature):
        raise llm._RateLimited("gemini rate limited")

    def fake_groq_chat(system, user, max_tokens, temperature):
        raise llm._RateLimited("groq rate limited")

    monkeypatch.setattr(llm, "_gemini_chat", fake_gemini_chat)
    monkeypatch.setattr(llm, "_groq_chat", fake_groq_chat)

    with pytest.raises(llm.LLMUnavailableError):
        llm.chat("system prompt", "unique query two", use_cache=False)
