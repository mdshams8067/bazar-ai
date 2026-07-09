"""
tests/test_chat.py — Integration tests for routers/chat.py.

Monkeypatches routers.chat.run_agent so these tests never make a real LLM
call — agent/pipeline.py's own behavior (matching, substitution, etc.) is
already covered end-to-end by agent/test_agent.py against the real LLM.
What's under test here is the router's job: merging matched products into
the real cart, handling LLMUnavailableError gracefully, and surviving a
per-item cart conflict without dropping the rest of the response.
"""
import pytest
from httpx import AsyncClient

import routers.chat as chat_module
from agent.matcher import Match, ParsedIngredient
from agent.pipeline import AgentResult, ParsedRequest
from core.llm import LLMUnavailableError
from models.product import Product
from tests.conftest import signup_user


def _fake_result(intent: str, matches: list[Match], reply: str = "Here's what I found.") -> AgentResult:
    parsed = ParsedRequest(
        intent=intent,
        dish_name="test dish",
        servings=4,
        serving_unit="people",
        budget_bdt=None,
        ingredients=[ParsedIngredient(name_en="test ingredient")],
        reply_context=reply,
    )
    return AgentResult(
        reply=reply,
        intent=intent,
        matches=matches,
        cart_actions=[],
        totals={"subtotal_bdt": 0.0, "item_count": 0},
        unmatched=[],
        parsed=parsed,
    )


async def test_chat_merges_matched_product_into_real_cart(
    client: AsyncClient, seeded_products: list[Product], monkeypatch: pytest.MonkeyPatch
) -> None:
    rice = seeded_products[0]  # stock_qty=10, price_bdt=190.0

    async def fake_run_agent(message: str, db, history=None) -> AgentResult:
        match = Match(product=rice, status="ok", quantity=2, line_total=380.0, note=None)
        return _fake_result("cook_dish", [match], reply="Added your rice.")

    monkeypatch.setattr(chat_module, "run_agent", fake_run_agent)

    token = await signup_user(client)
    resp = await client.post(
        "/chat", json={"message": "morog polao for 4"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Added your rice."
    assert body["matches"][0]["product"]["name_en"] == rice.name_en
    assert body["cart"]["item_count"] == 1
    assert body["cart"]["subtotal_bdt"] == 380.0


async def test_chat_llm_unavailable_returns_friendly_message_not_500(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_run_agent(message: str, db, history=None) -> AgentResult:
        raise LLMUnavailableError("both providers rate-limited")

    monkeypatch.setattr(chat_module, "run_agent", failing_run_agent)

    token = await signup_user(client, email="overloaded@example.com")
    resp = await client.post(
        "/chat", json={"message": "anything"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert "overloaded" in resp.json()["reply"].lower()


async def test_chat_cart_conflict_does_not_crash_whole_response(
    client: AsyncClient, seeded_products: list[Product], monkeypatch: pytest.MonkeyPatch
) -> None:
    out_of_stock_oil = seeded_products[1]  # stock_qty=0

    async def fake_run_agent(message: str, db, history=None) -> AgentResult:
        # The agent itself only returns in-stock matches in practice, but the
        # router must stay defensive regardless (see routers/chat.py).
        match = Match(product=out_of_stock_oil, status="ok", quantity=1, line_total=199.0, note=None)
        return _fake_result("add_items", [match], reply="Added your oil.")

    monkeypatch.setattr(chat_module, "run_agent", fake_run_agent)

    token = await signup_user(client, email="conflict@example.com")
    resp = await client.post(
        "/chat", json={"message": "add oil"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert "in stock" in resp.json()["reply"]
    assert resp.json()["cart"]["item_count"] == 0
