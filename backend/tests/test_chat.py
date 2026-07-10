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


async def test_chat_keep_only_items_removes_everything_else(
    client: AsyncClient, seeded_products: list[Product], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test: "only keep the rice, remove the rest" must remove
    every OTHER cart item and leave the named one(s) alone — not clear the
    whole cart, including the item the customer explicitly asked to keep."""
    rice, _oil, eggs = seeded_products
    token = await signup_user(client, email="keeponly@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/cart/items", json={"product_id": rice.id, "quantity": 1}, headers=headers)
    await client.post("/cart/items", json={"product_id": eggs.id, "quantity": 1}, headers=headers)

    async def fake_run_agent(message: str, db, history=None) -> AgentResult:
        parsed = ParsedRequest(
            intent="keep_only_items",
            dish_name=None,
            servings=None,
            serving_unit="people",
            budget_bdt=None,
            ingredients=[ParsedIngredient(name_en="rice")],
            reply_context="Keeping only the rice.",
        )
        return AgentResult(
            reply="Keeping only the rice.",
            intent="keep_only_items",
            matches=[],
            cart_actions=[],
            totals={"subtotal_bdt": 0.0, "item_count": 0},
            unmatched=[],
            parsed=parsed,
        )

    monkeypatch.setattr(chat_module, "run_agent", fake_run_agent)

    resp = await client.post("/chat", json={"message": "only keep the rice"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["cart"]["item_count"] == 1
    assert body["cart"]["items"][0]["product"]["name_en"] == rice.name_en
    assert "removed" in body["reply"].lower()


async def test_chat_keep_only_items_with_no_match_leaves_cart_untouched(
    client: AsyncClient, seeded_products: list[Product], monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the named "keep" item doesn't match anything in the cart, refuse
    to guess — leave the cart as is rather than risk emptying it."""
    rice, _oil, eggs = seeded_products
    token = await signup_user(client, email="keeponlymiss@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/cart/items", json={"product_id": rice.id, "quantity": 1}, headers=headers)
    await client.post("/cart/items", json={"product_id": eggs.id, "quantity": 1}, headers=headers)

    async def fake_run_agent(message: str, db, history=None) -> AgentResult:
        parsed = ParsedRequest(
            intent="keep_only_items",
            dish_name=None,
            servings=None,
            serving_unit="people",
            budget_bdt=None,
            ingredients=[ParsedIngredient(name_en="nonexistent product")],
            reply_context="Keeping only that item.",
        )
        return AgentResult(
            reply="Keeping only that item.",
            intent="keep_only_items",
            matches=[],
            cart_actions=[],
            totals={"subtotal_bdt": 0.0, "item_count": 0},
            unmatched=[],
            parsed=parsed,
        )

    monkeypatch.setattr(chat_module, "run_agent", fake_run_agent)

    resp = await client.post("/chat", json={"message": "only keep the nonexistent product"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["cart"]["item_count"] == 2
    assert "left it as is" in body["reply"].lower()


async def test_chat_modify_dish_swaps_cart_item(
    client: AsyncClient, seeded_products: list[Product], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test: "make it eggs instead of rice" must remove the old
    ingredient AND add the new one in the same turn — not just pile the
    new item on top while leaving the old one (and definitely not silently
    forget the swap, which is the exact bug this intent was built to fix:
    the LLM used to have nowhere to express "swap X for Y" at all, so a
    request like "make it beef" fell back to a fresh cook_dish/add_items
    that only ever adds, never removes)."""
    rice, _oil, eggs = seeded_products
    token = await signup_user(client, email="modifydish@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/cart/items", json={"product_id": rice.id, "quantity": 1}, headers=headers)

    async def fake_run_agent(message: str, db, history=None) -> AgentResult:
        parsed = ParsedRequest(
            intent="modify_dish",
            dish_name="test dish",
            servings=4,
            serving_unit="people",
            budget_bdt=None,
            ingredients=[ParsedIngredient(name_en="eggs")],
            remove_ingredients=[ParsedIngredient(name_en="rice")],
            reply_context="Swapping rice for eggs.",
        )
        match = Match(product=eggs, status="ok", quantity=2, line_total=300.0, note=None)
        return AgentResult(
            reply="Swapping rice for eggs.",
            intent="modify_dish",
            matches=[match],
            cart_actions=[],
            totals={"subtotal_bdt": 300.0, "item_count": 1},
            unmatched=[],
            parsed=parsed,
        )

    monkeypatch.setattr(chat_module, "run_agent", fake_run_agent)

    resp = await client.post("/chat", json={"message": "make it eggs instead of rice"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["cart"]["item_count"] == 1
    assert body["cart"]["items"][0]["product"]["name_en"] == eggs.name_en
    assert "removed" in body["reply"].lower()
    assert rice.name_en in body["reply"]


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
