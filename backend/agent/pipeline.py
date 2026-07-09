"""
agent/pipeline.py — Orchestration: one LLM call -> JSON parse -> matching -> assembly.

The LLM decides *what* (ingredients, quantities, intent); everything below it
in this module is deterministic code deciding *facts* (matches, stock,
totals, the chat reply). No second LLM call is used to phrase the reply —
it's assembled from templates so it stays reliable and free.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.matcher import (
    Match,
    ParsedIngredient,
    best_size_fit,
    find_pack_size_options,
    match_product,
    score_candidates,
    to_base,
)
from agent.prompts import SYSTEM_PROMPT
from agent.tools import CartAction, build_cart_actions, compute_cart_totals
from core import llm
from models.product import Product

logger = logging.getLogger(__name__)

_JSON_RETRY_INSTRUCTION = (
    "Your previous response was not valid JSON. Return only the JSON object, "
    "matching the schema exactly, with no markdown fences or commentary."
)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_UNMATCHED_STATUSES = {"unmatched", "unavailable_essential", "error"}

# Conversation memory is a bounded sliding window, not the full transcript —
# keeps token growth per call flat regardless of how long a session runs.
# ~6 messages (3 exchanges) is enough to resolve "remove it"/"still there"
# follow-ups without meaningfully eating into the free-tier token budget
# (measured: ~350 tokens for 3 exchanges against a ~1.8K-token system
# prompt — a real but small overhead, not the "extra LLM call" the
# original quota-discipline decision was actually worried about).
_MAX_HISTORY_MESSAGES = 6
_MAX_HISTORY_ENTRY_CHARS = 300


def _build_prompt(user_message: str, history: list[dict] | None) -> str:
    """Prepends a bounded window of recent turns so the LLM can resolve
    follow-ups naturally. Returns the bare message unchanged if there's no
    history (identical behavior to before memory existed)."""
    if not history:
        return user_message

    recent = history[-_MAX_HISTORY_MESSAGES:]
    lines = ["Conversation so far:"]
    for turn in recent:
        speaker = "Customer" if turn.get("role") == "user" else "Bazar Buddy"
        text = str(turn.get("text") or "")[:_MAX_HISTORY_ENTRY_CHARS]
        if text:
            lines.append(f"{speaker}: {text}")
    lines.append("")
    lines.append("New message from the customer:")
    lines.append(user_message)
    return "\n".join(lines)


@dataclass
class ParsedRequest:
    """The LLM's structured interpretation of one chat message."""

    intent: str
    dish_name: str | None
    servings: int | None
    serving_unit: str
    budget_bdt: float | None
    ingredients: list[ParsedIngredient]
    reply_context: str
    # Kept separate from reply_context specifically so the reply template
    # can put it LAST, after the facts (added/substituted/skipped) — a
    # question up front, answered by unrelated facts afterward, reads as
    # incoherent (this was a real UX complaint, not a style nitpick).
    followup_question: str | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> ParsedRequest:
        return cls(
            intent=str(raw.get("intent") or "other"),
            dish_name=raw.get("dish_name"),
            servings=raw.get("servings"),
            serving_unit=str(raw.get("serving_unit") or "people"),
            budget_bdt=raw.get("budget_bdt"),
            ingredients=[ParsedIngredient.from_dict(i) for i in (raw.get("ingredients") or [])],
            reply_context=str(raw.get("reply_context") or ""),
            followup_question=raw.get("followup_question") or None,
        )


@dataclass
class AgentResult:
    """Everything the chat router needs: the reply text plus the structured
    data behind it."""

    reply: str
    intent: str
    matches: list[Match]
    cart_actions: list[CartAction]
    totals: dict
    unmatched: list[Match]
    parsed: ParsedRequest


def _extract_json(text: str) -> dict:
    """Parses a JSON object out of the LLM's response, tolerating stray
    markdown fences the model sometimes adds despite instructions."""
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    return json.loads(cleaned)


async def _call_llm_for_json(user_message: str) -> dict:
    """Exactly one LLM call per message in the common case; a single
    re-prompt retry only fires if the first response fails to parse.
    Uses achat() (never the blocking chat()) since this runs inside an
    async def route — a blocking network call here would stall the event
    loop for every other concurrent request."""
    raw = await llm.achat(SYSTEM_PROMPT, user_message, temperature=0.2)
    try:
        return _extract_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"[pipeline] JSON parse failed, retrying once: {e}")
        retry_user = f"{user_message}\n\nPrevious response:\n{raw}\n\n{_JSON_RETRY_INSTRUCTION}"
        raw_retry = await llm.achat(SYSTEM_PROMPT, retry_user, temperature=0.2, use_cache=False)
        return _extract_json(raw_retry)  # a second failure propagates as-is


def _match_ingredients(
    ingredients: list[ParsedIngredient], catalog: list[Product], ask_pack_size: bool = False
) -> list[Match]:
    """Matches every ingredient; a failure on one never aborts the rest.

    ask_pack_size (add_items only): if the customer named a product but
    didn't state a size, and that product genuinely comes in more than
    one real pack size in stock, returns a "needs_clarification" match
    instead of silently guessing — the frontend renders the actual
    options as buttons, and nothing is added to the cart until the
    customer picks one. Full recipes (cook_dish) skip this: asking a
    clarifying question per ingredient there would mean answering half a
    dozen questions to get a bowl of polao going.
    """
    matches = []
    for ing in ingredients:
        try:
            if ask_pack_size and not ing.quantity_stated:
                options = find_pack_size_options(ing, catalog)
                if options:
                    matches.append(
                        Match(
                            product=None,
                            status="needs_clarification",
                            candidates=options,
                            note=f"Which size {ing.name_en} would you like? Pick an option below.",
                        )
                    )
                    continue
            matches.append(match_product(ing, catalog))
        except Exception:
            logger.exception(f"[pipeline] matching failed for ingredient: {ing.name_en}")
            matches.append(
                Match(product=None, status="error", note=f"Something went wrong matching {ing.name_en}.")
            )
    return matches


def _apply_budget(
    matches: list[Match],
    ingredients: list[ParsedIngredient],
    catalog: list[Product],
    budget_bdt: float,
) -> list[Match]:
    """If the matched cart exceeds budget, swaps the priciest swappable line
    items for the cheapest in-stock same-category candidate, most expensive
    first, until under budget or no swap helps further. Never drops an
    essential ingredient just to hit the number — an honest over-budget
    total is reported instead by the reply assembler."""
    total = sum(m.line_total for m in matches)
    if total <= budget_bdt:
        return matches

    order = sorted(range(len(matches)), key=lambda i: matches[i].line_total, reverse=True)

    for i in order:
        if total <= budget_bdt:
            break
        match, ing = matches[i], ingredients[i]
        if match.product is None:
            continue

        need_dim, _ = to_base(ing.quantity_unit, ing.quantity)
        pool = [p for p in catalog if p.category == ing.category_hint and p.stock_qty > 0]
        scored = score_candidates(pool, ing.search_terms, primary_term=ing.name_en)
        cheaper_pool = [
            p for _, p in scored if p.id != match.product.id and to_base(p.unit, p.unit_value)[0] == need_dim
        ]
        if not cheaper_pool:
            continue

        cheapest = min(cheaper_pool, key=lambda p: p.price_bdt / max(p.unit_value, 1e-9))
        product, qty = best_size_fit([cheapest], ing)
        new_line_total = round(product.price_bdt * qty, 2)
        if new_line_total >= match.line_total:
            continue  # no real savings, leave it

        total = total - match.line_total + new_line_total
        matches[i] = Match(
            product=product,
            status="ok",
            quantity=qty,
            line_total=new_line_total,
            note=f"Swapped to {product.name_en} to help fit your budget",
        )

    return matches


def _format_pack(unit: str, unit_value: float) -> str:
    value = int(unit_value) if unit_value == int(unit_value) else unit_value
    if unit == "pcs":
        return f"{value} pc" + ("" if value == 1 else "s")
    return f"{value}{unit}"


def _ensure_sentence(text: str) -> str:
    """Guarantees terminal punctuation so joined parts read as separate
    sentences instead of running into each other with no boundary."""
    text = text.strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _assemble_reply(parsed: ParsedRequest, matches: list[Match], totals: dict) -> str:
    """Builds the short summary line for the chat bubble — templates, not
    a second LLM call. Deliberately does NOT repeat each ingredient's
    substitution/skip note here: those are already shown, clearly and
    individually, on that ingredient's own match card in the UI. Folding
    them into this paragraph too was pure duplication, and duplicated
    template sentences with no punctuation between them is exactly what
    read as an incoherent wall of text. The follow-up question is also
    handled separately (see AgentResult.parsed.followup_question) so the
    frontend can place it after the match cards, not before them."""
    if parsed.intent == "product_question":
        match = matches[0] if matches else None
        if match and match.product:
            stock_note = "in stock" if match.product.stock_qty > 0 else "currently out of stock"
            return (
                f"{match.product.name_en} is ৳{match.product.price_bdt:.2f} "
                f"and {stock_note} ({match.product.stock_qty} available)."
            )
        return "Sorry, I couldn't find that product in our catalog."

    parts = [_ensure_sentence(parsed.reply_context)] if parsed.reply_context else []

    added = [m for m in matches if m.product is not None]
    if parsed.intent == "add_items" and added:
        # Named-product requests deserve an explicit confirmation of the
        # exact real product + pack size matched — e.g. ketchup comes in
        # several genuinely different sizes, and the customer shouldn't
        # have to guess (or dig through the match cards) to find out
        # which one was actually added.
        descriptions = [
            f"{m.product.name_en} ({_format_pack(m.product.unit, m.product.unit_value)}, x{m.quantity:g})"
            for m in added
        ]
        parts.append(f"Added {', '.join(descriptions)} — subtotal ৳{totals['subtotal_bdt']:.2f}.")
    elif added:
        parts.append(f"Added {len(added)} item(s) to your cart — subtotal ৳{totals['subtotal_bdt']:.2f}.")

    if parsed.intent == "budget_dish" and parsed.budget_bdt:
        if totals["subtotal_bdt"] <= parsed.budget_bdt:
            parts.append(f"That's within your ৳{parsed.budget_bdt:.0f} budget.")
        else:
            parts.append(
                f"I couldn't fit everything under ৳{parsed.budget_bdt:.0f} — "
                f"the closest I could get is ৳{totals['subtotal_bdt']:.2f} for these items."
            )

    return " ".join(parts)


async def run_agent(
    user_message: str, db: AsyncSession, history: list[dict] | None = None
) -> AgentResult:
    """Runs the full Bazar Buddy pipeline for one chat message: one LLM
    call, deterministic matching/substitution/budgeting, template reply.

    `history` is an optional bounded window of recent turns
    ([{"role": "user"|"assistant", "text": str}, ...]) — still exactly
    one LLM call, just a richer prompt, so the conversation can resolve
    natural follow-ups ("remove it", "it's still there") instead of
    treating every message as the first one."""
    prompt = _build_prompt(user_message, history)
    parsed_raw = await _call_llm_for_json(prompt)
    parsed = ParsedRequest.from_dict(parsed_raw)
    logger.info(
        f"[pipeline] intent={parsed.intent} dish={parsed.dish_name} "
        f"servings={parsed.servings} ingredients={len(parsed.ingredients)}"
    )

    # remove_items/clear_cart target the user's existing CART, not the
    # catalog — there's nothing here for match_product() to do. The router
    # (routers/chat.py) handles the actual cart mutation using
    # parsed.ingredients (still available via AgentResult.parsed below).
    if parsed.intent in ("other", "remove_items", "clear_cart") or not parsed.ingredients:
        return AgentResult(
            reply=parsed.reply_context or "How can I help you shop today?",
            intent=parsed.intent,
            matches=[],
            cart_actions=[],
            totals={"subtotal_bdt": 0.0, "item_count": 0},
            unmatched=[],
            parsed=parsed,
        )

    catalog = list((await db.execute(select(Product))).scalars().all())
    matches = _match_ingredients(parsed.ingredients, catalog, ask_pack_size=(parsed.intent == "add_items"))

    if parsed.intent == "budget_dish" and parsed.budget_bdt:
        matches = _apply_budget(matches, parsed.ingredients, catalog, parsed.budget_bdt)

    cart_actions = build_cart_actions(matches)
    totals = compute_cart_totals(cart_actions)
    unmatched = [m for m in matches if m.status in _UNMATCHED_STATUSES]
    reply = _assemble_reply(parsed, matches, totals)

    return AgentResult(
        reply=reply,
        intent=parsed.intent,
        matches=matches,
        cart_actions=cart_actions,
        totals=totals,
        unmatched=unmatched,
        parsed=parsed,
    )
