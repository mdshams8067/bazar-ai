"""
routers/chat.py — Bazar Buddy: the AI shopping assistant endpoint.

Thin wrapper around agent/pipeline.py's run_agent() — the LLM decides
*what* (ingredients, quantities, intent) inside that already-tested
pipeline; this router's only job is to run it, merge any matched products
into the user's real cart (through the same upsert_cart_item() path
routers/cart.py's own POST /cart/items uses — not a parallel
implementation), and return the structured result the frontend renders.

Requires auth: matched ingredients need a real user cart to merge into,
same as routers/cart.py. Chatting before login (a guest session/cart) is
a documented limitation, not an oversight — out of scope for a 3-day
take-home.
"""
from __future__ import annotations

import logging
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent.matcher import Match, ParsedIngredient
from agent.pipeline import run_agent
from core.database import get_db
from core.llm import LLMUnavailableError
from core.security import get_current_user
from models.cart_item import AddedVia, CartItem
from models.user import User
from routers.cart import load_cart, to_cart_read, upsert_cart_item
from schemas.cart import CartRead
from schemas.product import ProductRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Statuses whose matched product actually gets merged into the cart.
_ADDED_STATUSES = {"ok", "substituted_brand", "substituted_functional"}


class ChatHistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatRequest(BaseModel):
    message: str
    # A bounded window of recent turns (frontend already keeps the full
    # session in local state — this just replays the last few so the LLM
    # can resolve follow-ups like "remove it"). Optional and defaults to
    # empty so this stays backward compatible with a bare {message}.
    history: list[ChatHistoryTurn] = []


class MatchRead(BaseModel):
    product: ProductRead | None
    status: str
    quantity: float
    line_total: float
    note: str | None
    # Only set for status="needs_clarification" — the real pack-size
    # options the customer can pick from (see agent/matcher.py's
    # find_pack_size_options). The frontend renders these as buttons;
    # nothing is added to the cart until one is picked.
    candidates: list[ProductRead] | None = None


class ChatResponse(BaseModel):
    reply: str
    intent: str
    matches: list[MatchRead]
    cart: CartRead
    servings: int | None = None
    # What `servings` counts — "people" normally, but e.g. "days" if the
    # customer framed the request as a duration/supply instead of a
    # per-person dish (see agent/prompts.py). Lets the frontend label a
    # "scale it" control correctly instead of always assuming people.
    serving_unit: str = "people"
    # Kept separate from `reply` on purpose: the frontend renders this
    # AFTER the match cards, not folded into the same paragraph before
    # them — a question up front, "answered" by a wall of facts below it,
    # reads as incoherent (this was a direct, correct UX complaint).
    followup_question: str | None = None


def _match_to_read(m: Match) -> MatchRead:
    return MatchRead(
        product=ProductRead.model_validate(m.product) if m.product else None,
        status=m.status,
        quantity=m.quantity,
        line_total=m.line_total,
        note=m.note,
        candidates=[ProductRead.model_validate(p) for p in m.candidates] if m.candidates else None,
    )


def _find_cart_item_matches(ingredient: ParsedIngredient, cart_items: list[CartItem]) -> list[CartItem]:
    """Matches a removal-target ingredient against the user's CURRENT cart
    (not the catalog — there's nothing to match against there for a
    "remove this" request). Whole-word, case-insensitive match of the
    ingredient's name/search_terms against each cart item's product name —
    word-boundary, not a plain substring check, since a short term like
    "RD" (from "RD Banana Milk Drinks") is also a raw substring of
    unrelated words like "Cardamom". The cart is small enough that this
    doesn't need matcher.py's full scoring cascade, just this one guard."""
    terms = [t.lower() for t in ([ingredient.name_en, *ingredient.search_terms]) if t]
    patterns = [re.compile(rf"\b{re.escape(term)}\b") for term in terms]
    return [
        item
        for item in cart_items
        if any(pattern.search(item.product.name_en.lower()) for pattern in patterns)
    ]


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    try:
        history = [turn.model_dump() for turn in payload.history]
        result = await run_agent(payload.message, db, history=history)
    except LLMUnavailableError:
        # Both LLM providers failed — a friendly chat message, never a raw 500.
        logger.warning(f"[chat] LLM unavailable for user {current_user.id}")
        return ChatResponse(
            reply="I'm a bit overloaded — try again in a minute!",
            intent="other",
            matches=[],
            cart=to_cart_read(await load_cart(db, current_user.id)),
        )

    if result.intent == "clear_cart":
        cart_items = await load_cart(db, current_user.id)
        for item in cart_items:
            await db.delete(item)
        await db.commit()
        reply_parts = [result.parsed.reply_context] if result.parsed.reply_context else []
        reply_parts.append(
            f"Removed all {len(cart_items)} item(s)." if cart_items else "Your cart was already empty."
        )
        logger.info(f"[chat] clear_cart: removed {len(cart_items)} item(s) for user {current_user.id}")
        return ChatResponse(
            reply=" ".join(reply_parts),
            intent=result.intent,
            matches=[],
            cart=to_cart_read([]),
            followup_question=result.parsed.followup_question,
        )

    if result.intent == "remove_items":
        cart_items = await load_cart(db, current_user.id)
        removed_names: list[str] = []
        not_found_names: list[str] = []
        for ingredient in result.parsed.ingredients:
            found = _find_cart_item_matches(ingredient, cart_items)
            if not found:
                not_found_names.append(ingredient.name_en)
                continue
            for item in found:
                removed_names.append(item.product.name_en)
                await db.delete(item)
                cart_items.remove(item)  # don't let a later ingredient re-match an already-removed row
        await db.commit()
        logger.info(f"[chat] remove_items: removed {removed_names}, not found {not_found_names}")

        reply_parts = [result.parsed.reply_context] if result.parsed.reply_context else []
        if removed_names:
            reply_parts.append(f"Removed {', '.join(removed_names)} from your cart.")
        if not_found_names:
            reply_parts.append(f"Couldn't find {', '.join(not_found_names)} in your cart.")
        if not removed_names and not not_found_names:
            reply_parts.append("Nothing to remove.")
        return ChatResponse(
            reply=" ".join(reply_parts),
            intent=result.intent,
            matches=[],
            cart=to_cart_read(await load_cart(db, current_user.id)),
            followup_question=result.parsed.followup_question,
        )

    # Merge matched products into the user's real cart. Each upsert is
    # defensive on its own — one conflict (e.g. two ingredients resolving
    # to the same product and together exceeding stock) shouldn't drop the
    # rest of an otherwise-successful cart update.
    conflict_notes: list[str] = []
    for m in result.matches:
        if m.status in _ADDED_STATUSES and m.product is not None and m.quantity > 0:
            try:
                await upsert_cart_item(
                    db,
                    user_id=current_user.id,
                    product_id=m.product.id,
                    quantity=int(m.quantity),
                    added_via=AddedVia.assistant,
                    substitution_note=m.note,
                )
            except HTTPException as e:
                conflict_notes.append(str(e.detail))

    await db.commit()

    reply = result.reply
    if conflict_notes:
        reply = f"{reply} {' '.join(conflict_notes)}"

    return ChatResponse(
        reply=reply,
        intent=result.intent,
        matches=[_match_to_read(m) for m in result.matches],
        cart=to_cart_read(await load_cart(db, current_user.id)),
        servings=result.parsed.servings,
        serving_unit=result.parsed.serving_unit,
        followup_question=result.parsed.followup_question,
    )
