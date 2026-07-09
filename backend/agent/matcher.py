"""
agent/matcher.py — Ingredient -> product matching cascade.

Deterministic: given an ingredient parsed from the LLM's JSON, finds the best
real catalog product. Never invents a product; only picks among rows already
in the database. See prompts.py for the LLM output schema this consumes.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from statistics import median

from rapidfuzz import fuzz

from models.product import Product

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 85

# unit -> (dimension, base-unit multiplier). Base units: gram, ml, piece.
_UNIT_BASE: dict[str, tuple[str, float]] = {
    "kg": ("weight", 1000.0),
    "gm": ("weight", 1.0),
    "ltr": ("volume", 1000.0),
    "ml": ("volume", 1.0),
    "pcs": ("count", 1.0),
}


@dataclass
class ParsedIngredient:
    """One ingredient entry from the LLM's structured output."""

    name_en: str
    search_terms: list[str] = field(default_factory=list)
    category_hint: str = "other"
    quantity: float = 1.0
    quantity_unit: str = "pcs"
    quantity_stated: bool = False
    essential: bool = True
    substitute_hint: str | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> ParsedIngredient:
        """Builds a ParsedIngredient defensively — missing/odd fields fall
        back to sane defaults rather than raising, since the LLM's output
        shape can drift."""
        return cls(
            name_en=str(raw.get("name_en") or "item"),
            search_terms=[str(t) for t in (raw.get("search_terms") or [])] or [str(raw.get("name_en") or "item")],
            category_hint=str(raw.get("category_hint") or "other"),
            quantity=_safe_float(raw.get("quantity"), default=1.0),
            quantity_unit=str(raw.get("quantity_unit") or "pcs"),
            quantity_stated=bool(raw.get("quantity_stated", False)),
            essential=bool(raw.get("essential", True)),
            substitute_hint=raw.get("substitute_hint") or None,
        )


@dataclass
class Match:
    """Result of matching one ingredient to the catalog."""

    product: Product | None
    status: str  # ok | substituted_brand | substituted_functional | skipped_optional | unavailable_essential | unmatched | error | needs_clarification
    quantity: float = 0.0
    line_total: float = 0.0
    note: str | None = None
    # Only set for status="needs_clarification" — the distinct pack-size
    # options the customer can pick from (see find_pack_size_options).
    candidates: list[Product] | None = None


def _safe_float(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def to_base(unit: str, value: float) -> tuple[str, float]:
    """Converts a (unit, value) pair to a (dimension, base-unit-value) pair.
    Public — also used by pipeline.py's budget swap to avoid comparing
    prices across incompatible dimensions (e.g. a per-kg need against a
    per-piece novelty product)."""
    dimension, factor = _UNIT_BASE.get(unit, ("count", 1.0))
    return dimension, value * factor


def _term_score(name_lower: str, terms_lower: list[str], primary_lower: str | None = None) -> int:
    """Higher score for longer / whole-word term matches. A match on
    `primary_lower` (the ingredient's own name_en — its single canonical
    descriptor) gets a large flat bonus on top of the usual length-based
    score. This matters because length alone can't tell "specific" from
    "coincidentally long": e.g. for the ingredient "beef", search_terms
    might include "mangsho" (Bangla for "meat" broadly, not beef
    specifically) — a 7-letter word that would otherwise outscore the
    4-letter but exact "beef", letting it silently outrank real beef
    products against something unrelated like "Khashir Mangsho (Mutton
    Premium)" that also happens to contain "mangsho". Anchoring the bonus
    to the ingredient's own canonical name fixes this without needing a
    hand-maintained stopword list."""
    score = 0
    for term in terms_lower:
        if not term:
            continue
        if re.search(rf"\b{re.escape(term)}\b", name_lower):
            score += len(term) * 10 + 5
        elif term in name_lower:
            score += len(term) * 10

    if primary_lower and re.search(rf"\b{re.escape(primary_lower)}\b", name_lower):
        score += 150

    return score


def score_candidates(
    pool: list[Product], search_terms: list[str], primary_term: str | None = None
) -> list[tuple[int, Product]]:
    """Scores every product in `pool` whose name contains at least one
    search term (or the primary term), by term-match strength + price-per-
    unit sanity (guards against noisy cross-category matches when the
    category filter fell back to the whole catalog). Stock is deliberately
    NOT part of the score — relevance ranking must stay stock-blind so a
    stocked product never silently outranks a more relevant out-of-stock
    one; match_product() handles stock itself and surfaces any swap
    explicitly. `primary_term` (typically the ingredient's name_en) gets
    priority over plain search_terms — see _term_score. Returns
    (score, product) sorted descending (ties broken by product id, so
    results are reproducible), empty if nothing matched."""
    terms_lower = [t.lower() for t in search_terms if t]
    primary_lower = primary_term.lower() if primary_term else None
    if not terms_lower and not primary_lower:
        return []

    # Price-per-BASE-unit (per gram/ml, via to_base), not price-per-raw-
    # unit_value. Without this normalization, a 1000ml carton (price /
    # 1000 = a small number) and a 200ml drink (price / 200 = a much
    # bigger number) get compared as if on the same scale, and the larger
    # pack gets unfairly flagged as a price "outlier" purely from the unit
    # mismatch — which was silently disqualifying legitimate large-pack
    # plain products (e.g. 1L milk) from ever ranking at the top, leaving
    # only small flavored/novelty packs standing.
    prices_per_base_unit = [
        p.price_bdt / to_base(p.unit, p.unit_value)[1] for p in pool if p.unit_value
    ]
    typical_price = median(prices_per_base_unit) if prices_per_base_unit else None

    scored: list[tuple[int, Product]] = []
    for p in pool:
        name_lower = p.name_en.lower()
        term_score = _term_score(name_lower, terms_lower, primary_lower)
        if term_score == 0:
            continue

        score = term_score
        if typical_price and p.unit_value:
            price_per_base = p.price_bdt / to_base(p.unit, p.unit_value)[1]
            ratio = price_per_base / typical_price
            if ratio > 5 or ratio < 0.2:
                score -= 20  # likely a mismatched/noisy product

        scored.append((score, p))

    # Tie-break by name length (word count) before falling back to id.
    # A generic ingredient like "milk" or "rice" genuinely matches dozens
    # of products at an identical term-score — plain milk and a flavored
    # milk drink both just contain the word "milk". Product id has zero
    # relevance signal for breaking that tie. Word count does: the plain/
    # generic version of a product tends to have the fewest extra
    # descriptor words (brand gimmicks, flavors, promo text like "Buy3
    # Get1"), while a more specific variant reads as a longer name for the
    # same core word match. Not perfect, but a real, general signal that
    # doesn't need a hand-maintained flavor blocklist.
    scored.sort(key=lambda pair: (-pair[0], len(pair[1].name_en.split()), pair[1].id))
    return scored


def fuzzy_match(pool: list[Product], search_terms: list[str]) -> list[Product]:
    """Fallback fuzzy match (rapidfuzz partial_ratio > threshold) used only
    when exact substring matching finds nothing."""
    terms_lower = [t.lower() for t in search_terms if t]
    if not terms_lower:
        return []

    scored: list[tuple[float, Product]] = []
    for p in pool:
        name_lower = p.name_en.lower()
        best_ratio = max(fuzz.partial_ratio(term, name_lower) for term in terms_lower)
        if best_ratio > FUZZY_THRESHOLD:
            scored.append((best_ratio, p))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [p for _, p in scored]


def best_size_fit(in_stock: list[Product], ingredient: ParsedIngredient) -> tuple[Product, float]:
    """Picks the pack size that best fits the needed quantity, and how many
    of that pack to buy.

    - Need 500gm, packs 1kg/2kg/10kg -> smallest pack >= need (the 1kg), qty 1.
    - Need exceeds every pack -> buy multiples of the best (largest) pack.
    - If no candidate shares the ingredient's unit dimension (e.g. a "pcs"
      product against a "kg" need), falls back to the first candidate, qty 1.
    """
    need_dim, need_base = to_base(ingredient.quantity_unit, ingredient.quantity)

    sized = []
    for p in in_stock:
        dim, pack_base = to_base(p.unit, p.unit_value)
        if dim == need_dim and pack_base > 0:
            sized.append((p, pack_base))

    if not sized:
        return in_stock[0], 1.0

    fits = [(p, pack_base) for p, pack_base in sized if pack_base >= need_base]
    if fits:
        product, _ = min(fits, key=lambda pair: pair[1])
        return product, 1.0

    product, pack_base = max(sized, key=lambda pair: pair[1])
    qty = math.ceil(need_base / pack_base)
    return product, float(qty)


def find_pack_size_options(ingredient: ParsedIngredient, catalog: list[Product]) -> list[Product]:
    """Returns the distinct in-stock pack sizes available for this
    ingredient's top-scoring match group, if there's more than one real
    size — e.g. ketchup genuinely comes in 250ml/500ml/1kg, and silently
    picking one of those is a meaningfully different amount, not just a
    cosmetic brand choice. Returns an empty list when there's only one
    size on offer (even across many brands), since picking a brand within
    one size is a lower-stakes choice the normal auto-match already
    handles fine — only real size ambiguity is worth interrupting for.
    """
    pool = [p for p in catalog if p.category == ingredient.category_hint]
    if not pool:
        pool = catalog

    scored = score_candidates(pool, ingredient.search_terms, primary_term=ingredient.name_en)
    if not scored:
        return []

    top_score = scored[0][0]
    top_tier = [p for score, p in scored if score == top_score]
    in_stock = [p for p in top_tier if p.stock_qty > 0]

    distinct_sizes: dict[tuple[str, float], Product] = {}
    for p in in_stock:
        key = (p.unit, p.unit_value)
        distinct_sizes.setdefault(key, p)

    if len(distinct_sizes) < 2:
        return []

    return sorted(distinct_sizes.values(), key=lambda p: to_base(p.unit, p.unit_value)[1])


def match_product(ingredient: ParsedIngredient, catalog: list[Product]) -> Match:
    """Matches one ingredient to a real catalog product, deterministically.

    Cascade: category filter -> exact term scoring -> fuzzy fallback ->
    best top-tier candidate (sized to fit) -> three-tier substitution.

    "Top tier" is the set of candidates tied for the highest relevance
    score (stock-blind, see score_candidates). Three outcomes:
    - top tier is entirely in stock -> direct match, no note.
    - top tier is a mix of in-stock and out-of-stock candidates -> the
      out-of-stock one(s) were the "natural" pick; an equally relevant
      in-stock alternative exists, so it's used with an explicit
      brand-substitution note (this is what fires for e.g. ACI Chinigura
      Rice out-of-stock / Chashi Chinigura Rice in stock).
    - top tier is entirely out of stock -> hand off to find_substitute()
      for the wider brand/functional/skip cascade.
    """
    pool = [p for p in catalog if p.category == ingredient.category_hint]
    if not pool:
        pool = catalog

    scored = score_candidates(pool, ingredient.search_terms, primary_term=ingredient.name_en)
    if not scored:
        scored = [(0, p) for p in fuzzy_match(pool, ingredient.search_terms)]
        scored.sort(key=lambda pair: (-pair[0], pair[1].id))

    if not scored:
        if not ingredient.essential:
            return Match(
                product=None,
                status="skipped_optional",
                note=f"Couldn't find {ingredient.name_en} in our catalog — it's optional for this dish, so I skipped it",
            )
        return Match(
            product=None,
            status="unmatched",
            note=f"Couldn't find \"{ingredient.name_en}\" in the catalog.",
        )

    top_score = scored[0][0]
    top_tier = [p for score, p in scored if score == top_score]

    in_stock_top = [p for p in top_tier if p.stock_qty > 0]
    oos_top = [p for p in top_tier if p.stock_qty == 0]

    if in_stock_top and not oos_top:
        product, qty = best_size_fit(in_stock_top, ingredient)
        return Match(
            product=product,
            status="ok",
            quantity=qty,
            line_total=round(product.price_bdt * qty, 2),
        )

    if in_stock_top and oos_top:
        product, qty = best_size_fit(in_stock_top, ingredient)
        reference = oos_top[0]
        logger.info(f"[matcher] brand substitution: {reference.name_en} -> {product.name_en}")
        return Match(
            product=product,
            status="substituted_brand",
            quantity=qty,
            line_total=round(product.price_bdt * qty, 2),
            note=f"{reference.name_en} is out of stock — added {product.name_en} instead",
        )

    # Every top-tier candidate is out of stock -> substitution tiers.
    from agent.stock import find_substitute  # local import breaks the circular dependency

    return find_substitute(ingredient, top_tier, catalog)
