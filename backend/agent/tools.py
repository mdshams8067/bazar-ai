"""
agent/tools.py — Turns matcher/stock results into cart actions.

Kept storage-agnostic on purpose: routers/cart.py (not yet built) owns the
persisted Cart/CartItem tables. These helpers produce plain dicts shaped like
a cart line item, which the chat router merges into the user's real cart.
"""
from __future__ import annotations

from dataclasses import dataclass

from agent.matcher import Match

# Statuses that represent a product actually added to the cart.
_ADDED_STATUSES = {"ok", "substituted_brand", "substituted_functional"}


@dataclass
class CartAction:
    """One line item resulting from a matched (or substituted) ingredient."""

    product_id: int
    name_en: str
    unit: str
    unit_value: float
    unit_price: float
    quantity: float
    line_total: float
    status: str
    note: str | None = None


def build_cart_actions(matches: list[Match]) -> list[CartAction]:
    """Converts matches with a real product and non-zero quantity into cart
    actions. Skipped/unavailable ingredients (no product) produce no action —
    the chat reply surfaces those via each Match's `note` instead."""
    actions = []
    for m in matches:
        if m.status not in _ADDED_STATUSES or m.product is None or m.quantity <= 0:
            continue
        actions.append(
            CartAction(
                product_id=m.product.id,
                name_en=m.product.name_en,
                unit=m.product.unit,
                unit_value=m.product.unit_value,
                unit_price=m.product.price_bdt,
                quantity=m.quantity,
                line_total=m.line_total,
                status=m.status,
                note=m.note,
            )
        )
    return actions


def compute_cart_totals(actions: list[CartAction]) -> dict:
    """Subtotal and item count for a list of cart actions."""
    return {
        "subtotal_bdt": round(sum(a.line_total for a in actions), 2),
        "item_count": len(actions),
    }


def merge_into_cart(cart: list[dict], actions: list[CartAction]) -> list[dict]:
    """Merges cart actions into an existing in-memory cart (list of
    {product_id, quantity} dicts — the shape a persisted Cart/CartItem table
    would round-trip), summing quantities for a product already present."""
    cart_by_product = {item["product_id"]: dict(item) for item in cart}
    for action in actions:
        existing = cart_by_product.get(action.product_id)
        if existing:
            existing["quantity"] += action.quantity
        else:
            cart_by_product[action.product_id] = {
                "product_id": action.product_id,
                "quantity": action.quantity,
            }
    return list(cart_by_product.values())
