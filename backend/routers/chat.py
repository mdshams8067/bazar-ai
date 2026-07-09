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
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent.matcher import Match
from agent.pipeline import run_agent
from core.database import get_db
from core.llm import LLMUnavailableError
from core.security import get_current_user
from models.cart_item import AddedVia
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
