"""
agent/pipeline.py — Orchestration: one LLM call -> JSON parse -> matching -> assembly.

The LLM decides *what* (ingredients, quantities, intent); everything below it
in this module is deterministic code deciding *facts* (matches, stock,
totals, the chat reply). No second LLM call is used to phrase the reply —
it's assembled from templates so it stays reliable and free.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field, replace

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.matcher import (
    Match,
    PantryItem,
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
from core.config import ENABLE_EMBEDDING_MATCH
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


def _as_dict_list(value: object) -> list[dict]:
    """Normalizes a schema field that's supposed to be a list of objects,
    since the LLM's output shape can drift — live and reproducible, not
    hypothetical: a "diy_substitute" field that should have been a
    one-item list came back as a single bare object instead, and
    iterating a dict directly yields its string keys, not the object
    itself, crashing the next .from_dict() call on a plain string. A
    lone dict is wrapped into a one-item list; anything else that isn't
    already a list of dicts is dropped rather than trusted."""
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


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
    # modify_dish only: the OLD ingredient(s) being swapped OUT of the
    # cart (matched against the current cart, like remove_items). Empty
    # for every other intent — `ingredients` above carries the NEW
    # ingredient(s) being swapped in, matched against the catalog like a
    # normal add.
    remove_ingredients: list[ParsedIngredient] = field(default_factory=list)
    # cook_dish/budget_dish only: items the customer says they already
    # have at home, extracted from a message answering the pantry-check
    # question (see run_agent's pantry gate). Empty for every other
    # intent, and empty whenever the current message isn't answering
    # that question at all — empty always means "proceed with the full
    # ingredient list as-is," never "assume nothing is owned" as a guess.
    pantry_items_owned: list[PantryItem] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict) -> ParsedRequest:
        return cls(
            intent=str(raw.get("intent") or "other"),
            dish_name=raw.get("dish_name"),
            servings=raw.get("servings"),
            serving_unit=str(raw.get("serving_unit") or "people"),
            budget_bdt=raw.get("budget_bdt"),
            ingredients=[ParsedIngredient.from_dict(i) for i in _as_dict_list(raw.get("ingredients"))],
            reply_context=str(raw.get("reply_context") or ""),
            followup_question=raw.get("followup_question") or None,
            remove_ingredients=[ParsedIngredient.from_dict(i) for i in _as_dict_list(raw.get("remove_ingredients"))],
            pantry_items_owned=[PantryItem.from_dict(i) for i in _as_dict_list(raw.get("pantry_items_owned"))],
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


# Recipes with several essential ingredients can each carry a diy_substitute
# array (2-4 components) on top of their normal fields — comfortably past
# llm.chat()'s 1024-token default for anything beyond a handful of
# ingredients, which was silently truncating the JSON mid-string (a real
# regression measured when this field was added, not a defensive guess).
_MAX_OUTPUT_TOKENS = 2048


async def _call_llm_for_json(user_message: str) -> dict:
    """Exactly one LLM call per message in the common case; a single
    re-prompt retry only fires if the first response fails to parse.
    Uses achat() (never the blocking chat()) since this runs inside an
    async def route — a blocking network call here would stall the event
    loop for every other concurrent request."""
    raw = await llm.achat(SYSTEM_PROMPT, user_message, max_tokens=_MAX_OUTPUT_TOKENS, temperature=0.2)
    try:
        return _extract_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"[pipeline] JSON parse failed, retrying once: {e}")
        retry_user = f"{user_message}\n\nPrevious response:\n{raw}\n\n{_JSON_RETRY_INSTRUCTION}"
        raw_retry = await llm.achat(
            SYSTEM_PROMPT, retry_user, max_tokens=_MAX_OUTPUT_TOKENS, temperature=0.2, use_cache=False
        )
        return _extract_json(raw_retry)  # a second failure propagates as-is


async def _embed_ingredients(ingredients: list[ParsedIngredient]) -> dict[int, tuple[list[float], str, str]]:
    """One batched embedding call for every ingredient in this message (not
    per-ingredient, not per-message-turn) — the Layer-1 retrieval addition
    described in match_product()'s docstring. Failure here (rate limit,
    provider outage) degrades to exact/fuzzy-only matching rather than
    failing the whole chat turn, since this is strictly a wider net, never
    the only way a match can succeed.

    Each ingredient's result carries the model that actually embedded it
    (core/gemini_client.py's key/model rotation means different ingredients
    in the same batch — or the same ingredient on a different day — can
    come back tagged with different models); match_product() and
    embedding_candidates() key off that per-ingredient model, never assume
    one model for the whole call. The plain query text travels alongside
    the vector too — embedding_candidates() reranks with it directly (see
    agent/embedding_match.py), not just the vector."""
    from core.embeddings import aembed_texts

    texts = [f"{ing.name_en} {' '.join(ing.search_terms)}".strip() for ing in ingredients]
    try:
        results = await aembed_texts(texts)
    except Exception:
        logger.exception("[pipeline] embedding lookup failed; continuing with exact/fuzzy matching only")
        return {}
    return {id(ing): (vec, model, text) for ing, (vec, model), text in zip(ingredients, results, texts)}


async def _match_ingredients(
    ingredients: list[ParsedIngredient],
    catalog: list[Product],
    ask_pack_size: bool = False,
    query_embeddings: dict[int, tuple[list[float], str, str]] | None = None,
) -> list[Match]:
    """Matches every ingredient concurrently; a failure on one never
    aborts the rest.

    ask_pack_size (add_items only): if the customer named a product but
    didn't state a size, and that product genuinely comes in more than
    one real pack size in stock, returns a "needs_clarification" match
    instead of silently guessing — the frontend renders the actual
    options as buttons, and nothing is added to the cart until the
    customer picks one. Full recipes (cook_dish) skip this: asking a
    clarifying question per ingredient there would mean answering half a
    dozen questions to get a bowl of polao going.

    query_embeddings (optional): id(ingredient) -> (embedding vector,
    model that produced it, plain query text), computed once up front in
    run_agent (a single batched async API call) rather than per
    ingredient here. match_product() itself is still a plain sync
    function (its embedding-tier calls to Jina/the LLM go through
    blocking `requests`, not an async client), so each ingredient's
    match is run in its own thread via asyncio.to_thread — measured live
    at up to ~2-3s per ingredient when it reaches the embedding tier
    (cosine + rerank + verification are all real network calls), which
    made a 9-ingredient dish take ~6s sequentially; concurrently, total
    time is close to the slowest single ingredient instead of the sum of
    all of them. Order of the returned list matches `ingredients`,
    exactly like the old sequential loop — asyncio.gather preserves
    argument order regardless of which task finishes first."""

    def _match_one(ing: ParsedIngredient) -> Match:
        try:
            if ask_pack_size and not ing.quantity_stated:
                options = find_pack_size_options(ing, catalog)
                if options:
                    return Match(
                        product=None,
                        status="needs_clarification",
                        candidates=options,
                        note=f"Which size {ing.name_en} would you like? Pick an option below.",
                    )
            query_embedding, query_embedding_model, query_text = (query_embeddings or {}).get(
                id(ing), (None, None, None)
            )
            return match_product(
                ing,
                catalog,
                query_embedding=query_embedding,
                query_embedding_model=query_embedding_model,
                query_text=query_text,
            )
        except Exception:
            logger.exception(f"[pipeline] matching failed for ingredient: {ing.name_en}")
            return Match(product=None, status="error", note=f"Something went wrong matching {ing.name_en}.")

    return list(await asyncio.gather(*(asyncio.to_thread(_match_one, ing) for ing in ingredients)))


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
        product, qty, exact = best_size_fit([cheapest], ing)
        new_line_total = round(product.price_bdt * qty, 2)
        if new_line_total >= match.line_total:
            continue  # no real savings, leave it

        total = total - match.line_total + new_line_total
        matches[i] = Match(
            product=product,
            status="ok",
            quantity=qty,
            line_total=new_line_total,
            size_approximated=not exact,
            note=f"Swapped to {product.name_en} to help fit your budget",
        )

    return matches


def _format_pack(unit: str, unit_value: float) -> str:
    value = int(unit_value) if unit_value == int(unit_value) else unit_value
    if unit == "pcs":
        return f"{value} pc" + ("" if value == 1 else "s")
    return f"{value}{unit}"


def _describe_match(m: Match) -> str:
    """One-line description of what a match actually added, for the
    explicit add_items/modify_dish confirmation. A "substituted_diy" match
    has no single product — describe its components instead."""
    if m.product:
        return f"{m.product.name_en} ({_format_pack(m.product.unit, m.product.unit_value)}, x{m.quantity:g})"
    if m.components:
        parts = [f"{c.product.name_en} (x{c.quantity:g})" for c in m.components]
        return f"{' + '.join(parts)} (substitute)"
    return ""


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
        # No real product to report a fact about. Prefer the match's own
        # note first — it's the deterministic, code-verified answer to
        # the actual question asked ("we don't carry tuna and couldn't
        # find a substitute"), not the generic "checking for you"
        # placeholder the LLM writes into reply_context before the real
        # lookup even runs (see the prompt rule for this intent) — that
        # placeholder is fine as a fallback, but stating the real finding
        # directly is a genuinely better answer whenever it's available.
        # reply_context is still the fallback for a genuinely
        # conversational question the LLM misclassified as
        # product_question instead of ingredient_question (a fine line,
        # e.g. "is paneer available?" vs "do I need paneer for this?").
        if match and match.note:
            return match.note
        return parsed.reply_context or "Sorry, I couldn't find that product in our catalog."

    parts = [_ensure_sentence(parsed.reply_context)] if parsed.reply_context else []

    # A "substituted_diy" match has no single product (see agent/stock.py)
    # but did add real components to the cart, so it counts as "added" too.
    added = [m for m in matches if m.product is not None or m.components]
    if parsed.intent in ("add_items", "modify_dish") and added:
        # Named-product requests deserve an explicit confirmation of the
        # exact real product + pack size matched — e.g. ketchup comes in
        # several genuinely different sizes, and the customer shouldn't
        # have to guess (or dig through the match cards) to find out
        # which one was actually added.
        descriptions = [_describe_match(m) for m in added]
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

    # unavailable_essential is qualitatively different from a routine
    # substitution or optional skip — it means the dish genuinely can't
    # be completed as asked, not just completed with a stand-in. Leaving
    # that to the match card alone (like every other note) let a reply
    # like "Added 2 item(s) to your cart" stand as the whole story when
    # the one ingredient that made the dish what it was — e.g. foie gras
    # for a foie gras terrine — never made it in at all. Calling this out
    # by name here doesn't reintroduce the "wall of text" problem that
    # motivated not repeating notes generally: it's specifically the one
    # failure severe enough to change whether "Added N items" reads as
    # good news or not.
    essential_failures = [
        ing.name_en for ing, m in zip(parsed.ingredients, matches) if m.status == "unavailable_essential"
    ]
    if essential_failures:
        if len(essential_failures) == 1:
            parts.append(
                f"Sorry, I couldn't get {essential_failures[0]} — no substitute worked either, "
                f"so you may want to source it elsewhere for this dish."
            )
        else:
            parts.append(
                f"Sorry, I couldn't get {', '.join(essential_failures)} — no substitute worked for "
                f"them either, so you may want to source them elsewhere for this dish."
            )

    # A generic disclaimer, not a per-item list: best_size_fit() flags
    # size_approximated whenever no real pack size hits the requested
    # quantity exactly, which is true for most small recipe amounts
    # against retail pack sizes (20gm salt against a 1kg bag is always
    # "approximated" — that's just how grocery packaging works, not a
    # matching problem) — naming every affected ingredient here would
    # mean listing most of a typical recipe every time. One quiet,
    # generic line covers it without turning into per-item noise.
    if any(m.size_approximated and m.product for m in matches):
        parts.append("Note: some items were added in the closest available pack size rather than an exact amount.")

    return " ".join(parts)


_CATALOG_CACHE_TTL_SECONDS = 30
_catalog_cache: tuple[float, list[Product]] | None = None


async def _load_catalog(db: AsyncSession) -> list[Product]:
    """Loads every product, including its embedding vector — measured
    live at ~14s to fetch all ~2,807 products' embeddings over the
    network to Supabase, the single biggest latency contributor once
    embedding retrieval became Layer 1's primary method (run on every
    chat message, not just a rare fallback case). Cached in memory for
    _CATALOG_CACHE_TTL_SECONDS, since the catalog changes rarely between
    requests. Stock can read up to this many seconds stale within that
    window, but that's an accepted, bounded trade-off, not a correctness
    risk: checkout independently re-validates real stock before an order
    is ever placed, regardless of what this cache shows a chat message.
    Cached rows are expunged from their loading session (`db.expunge_all`)
    so they stay safely readable after that session closes — every
    downstream use only reads already-loaded scalar columns (id, name_en,
    price, stock, embedding), never a lazy relationship, so a detached
    instance is exactly as usable as a session-bound one here."""
    global _catalog_cache
    now = time.monotonic()
    if _catalog_cache is not None and now - _catalog_cache[0] < _CATALOG_CACHE_TTL_SECONDS:
        return _catalog_cache[1]

    catalog = list((await db.execute(select(Product))).scalars().all())
    db.expunge_all()
    _catalog_cache = (now, catalog)
    return catalog


# Deliberately fixed, code-controlled text — never the LLM's own phrasing
# of this question (which the prompt still asks for in followup_question,
# but run_agent overrides before returning; see the pantry gate below).
# Needing this exact string to show up verbatim in conversation history
# is what lets the *next* turn cheaply and reliably detect "the previous
# assistant turn was this specific question" without adding any server-
# side session state — the whole app is already stateless between
# messages, reconstructing everything from history text each time (the
# same pattern modify_dish already relies on to recall what ingredient
# is being swapped out).
_PANTRY_QUESTION = (
    "Do you already have any of these at home? Let me know and I'll add the rest to your cart automatically."
)


def _awaiting_pantry_response(history: list[dict] | None) -> bool:
    """True when the immediately-preceding assistant turn asked the
    pantry-check question — i.e. this message is very likely answering
    it, not starting something new."""
    if not history:
        return False
    last = history[-1]
    return last.get("role") == "assistant" and _PANTRY_QUESTION in (last.get("text") or "")


# Matches this module's own breakdown format ("0.5kg aromatic rice",
# "1 pc biryani masala" — see _format_pack: no space before kg/gm/ltr/ml,
# one space before pc/pcs). Deliberately permissive on the name (anything
# up to the next comma/period) since dish ingredient names are free text.
_INGREDIENT_BREAKDOWN_RE = re.compile(r"([\d.]+)\s*(kg|gm|ltr|ml|pcs?)\s+([^,.]+)")


def _parse_ingredient_breakdown(text: str) -> dict[str, tuple[float, str]]:
    """Extracts {ingredient name (lowercase): (quantity, unit)} from a
    breakdown line this module itself generated (the pantry-gate reply,
    see run_agent). Used instead of trusting the LLM to recall the exact
    numbers it stated a turn earlier: live testing found it doesn't
    always do that consistently even when explicitly instructed to (a
    dish's onion need recomputed as 0.2kg on a follow-up turn when the
    original turn had already stated 0.3kg) — recalling a precise number
    from free text is exactly the kind of "fact," not "intent," this
    project's whole design keeps out of the LLM's hands elsewhere.
    Parsing our own deterministic output back out is just applying that
    same principle here."""
    return {
        name.strip().lower(): (float(qty), "pcs" if unit.startswith("pc") else unit)
        for qty, unit, name in _INGREDIENT_BREAKDOWN_RE.findall(text)
    }


def _find_pantry_match(ingredient: ParsedIngredient, owned: list[PantryItem]) -> PantryItem | None:
    """Matches a pantry item the customer named against one of the dish's
    real ingredients — plain substring first, fuzzy as a fallback (same
    token_sort_ratio approach as agent/matcher.py's fuzzy_match, reused
    here for the same reason: "rice" said in a pantry answer should match
    "aromatic rice" in the ingredient list without needing an exact
    string)."""
    ing_name = ingredient.name_en.lower()
    for item in owned:
        item_name = item.name_en.lower()
        if item_name in ing_name or ing_name in item_name:
            return item
    for item in owned:
        if fuzz.token_sort_ratio(ing_name, item.name_en.lower()) >= 70:
            return item
    return None


def _apply_pantry_adjustments(
    ingredients: list[ParsedIngredient], owned: list[PantryItem]
) -> list[ParsedIngredient]:
    """Reduces or drops ingredients the customer already has at home.

    - Named with no quantity ("I have rice") -> assumed enough, dropped
      entirely rather than guessing how much they actually have.
    - Named with a quantity that covers or exceeds the need -> also
      dropped entirely.
    - Named with a quantity smaller than the need, same unit dimension
      (e.g. "1kg" against a "kg" need) -> kept, but only for the deficit
      (need 2kg, have 1kg -> buy 1kg), so the customer isn't sold what
      they already own.
    - A unit-dimension mismatch (e.g. they said "2 pcs" against a "kg"
      need) can't be safely compared -> left at the full original need
      rather than guessed at.
    - Ingredients the customer didn't mention at all pass through
      unchanged."""
    if not owned:
        return ingredients

    adjusted: list[ParsedIngredient] = []
    for ing in ingredients:
        match = _find_pantry_match(ing, owned)
        if match is None:
            adjusted.append(ing)
            continue
        if match.quantity is None or match.quantity_unit is None:
            continue  # named with no amount -> assume they have enough

        need_dim, need_base = to_base(ing.quantity_unit, ing.quantity)
        have_dim, have_base = to_base(match.quantity_unit, match.quantity)
        if have_dim != need_dim:
            adjusted.append(ing)
            continue

        deficit_base = need_base - have_base
        if deficit_base <= 0:
            continue  # they already have enough

        _, per_unit_base = to_base(ing.quantity_unit, 1.0)
        deficit_in_ing_unit = deficit_base / per_unit_base
        adjusted.append(replace(ing, quantity=deficit_in_ing_unit, quantity_stated=True))

    return adjusted


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

    # remove_items/clear_cart/keep_only_items target the user's existing
    # CART, not the catalog — there's nothing here for match_product() to
    # do. The router (routers/chat.py) handles the actual cart mutation
    # using parsed.ingredients (still available via AgentResult.parsed
    # below). modify_dish is deliberately NOT in this list — its
    # "ingredients" (the NEW item being swapped in) DO need catalog
    # matching, same as add_items; only its "remove_ingredients" (the OLD
    # item being swapped out) are cart-only, and the router handles that
    # side separately. ingredient_question never has ingredients to match
    # at all (see prompts.py) — it's a conversational answer, not a cart
    # action — but it's listed here explicitly too, not just relying on
    # `not parsed.ingredients`, so a stray populated list from the LLM
    # can never accidentally trigger a real catalog/cart side effect for
    # what's supposed to be a pure question.
    if parsed.intent in ("other", "remove_items", "clear_cart", "keep_only_items", "ingredient_question") or not parsed.ingredients:
        return AgentResult(
            reply=parsed.reply_context or "How can I help you shop today?",
            intent=parsed.intent,
            matches=[],
            cart_actions=[],
            totals={"subtotal_bdt": 0.0, "item_count": 0},
            unmatched=[],
            parsed=parsed,
        )

    # A recipe request with no stated (or inferable) serving size still
    # got a real quantity for every ingredient before this gate existed —
    # the LLM always fills in *some* number, so "noodles banabo" with no
    # people mentioned silently guessed a serving size and added a full
    # cart's worth, in the same turn as asking "how many people are you
    # cooking for?" — a question with no reason to answer, since the
    # shopping had already happened. cook_dish/budget_dish specifically
    # (the two intents servings actually scales) skip matching entirely
    # and wait for the answer instead, exactly like the other pure-
    # question intents above. Only fires when the LLM itself couldn't
    # resolve servings from context (parsed.servings is None) and is
    # actually asking about it — a follow-up turn that includes serving
    # size in history resolves normally and proceeds straight through.
    if parsed.intent in ("cook_dish", "budget_dish") and parsed.servings is None and parsed.followup_question:
        # A deterministic reply, not parsed.reply_context: the LLM writes
        # that field assuming the normal flow (cart already filled), so
        # it tends to say things like "I've prepared an ingredient list"
        # — inaccurate and slightly confusing paired with a question
        # that hasn't been answered yet, since nothing was actually
        # prepared. Nothing here depends on LLM wording, so there's
        # nothing to get wrong turn to turn.
        dish = parsed.dish_name or "that"
        return AgentResult(
            reply=f"Happy to help with {dish}!",
            intent=parsed.intent,
            matches=[],
            cart_actions=[],
            totals={"subtotal_bdt": 0.0, "item_count": 0},
            unmatched=[],
            parsed=parsed,
        )

    # Once servings is known, a fresh cook_dish/budget_dish request still
    # needs one more answer before shopping: does the customer already
    # have any of these at home? (agent/prompts.py's own rule already has
    # the LLM ask this whenever nothing else is pending — this gate is
    # what makes the app actually wait for the answer instead of asking
    # while shopping anyway, the exact same problem the servings gate
    # above fixes for the previous question.) _awaiting_pantry_response
    # tells the two cases apart: True means the previous assistant turn
    # already asked this exact question, so this message is very likely
    # answering it — reconcile parsed.pantry_items_owned (empty just
    # means "proceed with the full list, nothing owned") into the
    # ingredient quantities and continue straight into matching. False
    # means this is the first time reaching this dish with servings
    # known — ask, and stop here without touching the catalog or cart.
    # Narrowly corrected before the check below, not broadly: live
    # testing found a plain "no, add everything" answering the pantry
    # question sometimes comes back classified as add_items instead of
    # staying cook_dish/budget_dish — which has different downstream
    # behavior (ask_pack_size=True triggers pack-size clarification
    # questions that don't belong in a recipe flow). Only correcting this
    # specific, observed drift (add_items, with a real ingredient list
    # already computed) rather than forcing every intent back to
    # cook_dish whenever the previous turn happened to ask about pantry
    # items — a customer genuinely changing the subject after that
    # question (e.g. asking a price) must NOT be dragged back into the
    # recipe flow just because of what the last turn asked.
    if _awaiting_pantry_response(history) and parsed.intent == "add_items" and parsed.ingredients:
        parsed.intent = "cook_dish"
    if parsed.intent in ("cook_dish", "budget_dish"):
        if _awaiting_pantry_response(history):
            # Use the quantities actually shown to the customer (parsed
            # back out of our own previous reply), not whatever this
            # turn's LLM call recomputed for the same dish — see
            # _parse_ingredient_breakdown's docstring for the live
            # inconsistency that motivated this.
            original = _parse_ingredient_breakdown(history[-1].get("text") or "")
            restored = []
            for ing in parsed.ingredients:
                found = original.get(ing.name_en.lower())
                if found is None:
                    for name, qty_unit in original.items():
                        if name in ing.name_en.lower() or ing.name_en.lower() in name:
                            found = qty_unit
                            break
                restored.append(replace(ing, quantity=found[0], quantity_unit=found[1]) if found else ing)
            parsed.ingredients = _apply_pantry_adjustments(restored, parsed.pantry_items_owned)
            parsed.followup_question = None
        else:
            breakdown = ", ".join(
                f"{_format_pack(ing.quantity_unit, ing.quantity)} {ing.name_en}" for ing in parsed.ingredients
            )
            dish = parsed.dish_name or "this"
            servings_desc = f" ({parsed.servings} {parsed.serving_unit})" if parsed.servings else ""
            parsed.followup_question = _PANTRY_QUESTION
            return AgentResult(
                reply=f"For {dish}{servings_desc}, you'll need: {breakdown}.",
                intent=parsed.intent,
                matches=[],
                cart_actions=[],
                totals={"subtotal_bdt": 0.0, "item_count": 0},
                unmatched=[],
                parsed=parsed,
            )

    catalog = await _load_catalog(db)

    query_embeddings: dict[int, tuple[list[float], str, str]] = {}
    if ENABLE_EMBEDDING_MATCH and parsed.ingredients:
        query_embeddings = await _embed_ingredients(parsed.ingredients)

    matches = await _match_ingredients(
        parsed.ingredients, catalog, ask_pack_size=(parsed.intent == "add_items"), query_embeddings=query_embeddings
    )

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
