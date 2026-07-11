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

from core.config import ENABLE_EMBEDDING_MATCH, ENABLE_EXACT_FUZZY_MATCH
from models.product import Product

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 70

# unit -> (dimension, base-unit multiplier). Base units: gram, ml, piece.
_UNIT_BASE: dict[str, tuple[str, float]] = {
    "kg": ("weight", 1000.0),
    "gm": ("weight", 1.0),
    "ltr": ("volume", 1000.0),
    "ml": ("volume", 1.0),
    "pcs": ("count", 1.0),
}


@dataclass
class SubstituteComponent:
    """One raw ingredient the LLM proposes as part of a DIY substitute
    recipe for an essential ingredient it expects might be unavailable
    (e.g. butter + milk standing in for heavy cream). Same shape as the
    relevant subset of ParsedIngredient — just enough to run through the
    normal catalog matcher for each component."""

    name_en: str
    search_terms: list[str] = field(default_factory=list)
    category_hint: str = "other"
    quantity: float = 1.0
    quantity_unit: str = "pcs"

    @classmethod
    def from_dict(cls, raw: dict) -> SubstituteComponent:
        return cls(
            name_en=str(raw.get("name_en") or "item"),
            search_terms=[str(t) for t in (raw.get("search_terms") or [])] or [str(raw.get("name_en") or "item")],
            category_hint=str(raw.get("category_hint") or "other"),
            quantity=_safe_float(raw.get("quantity"), default=1.0),
            quantity_unit=str(raw.get("quantity_unit") or "pcs"),
        )


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
    # Only meaningful when essential=True: a proposed DIY substitute recipe
    # (2-4 raw ingredients) if this one turns out to be unavailable and no
    # single-product substitute exists either. Proposed unconditionally by
    # the LLM alongside substitute_hint — same pattern, just multi-product —
    # and only ever used by the deterministic code as a last resort, after
    # brand and functional substitution both fail. See agent/stock.py.
    diy_substitute: list[SubstituteComponent] | None = None
    # True when the customer named a specific premium/rare variant of a
    # more generic ingredient (wagyu beef, saffron rice, black winter
    # truffle) rather than the everyday version. The matcher is keyword-
    # based — it has no idea "wagyu beef" and "beef" aren't the same
    # thing, so without this flag a catalog that (realistically) has no
    # wagyu at all silently matches ordinary beef and reports a clean
    # "ok", never telling the customer they didn't get what they asked
    # for. See _apply_specific_variant_check() in this module.
    is_specific_variant: bool = False
    # Only meaningful when is_specific_variant=True — the generic category
    # name a normal grocery catalog would actually carry (e.g. "beef" for
    # wagyu beef), used to phrase the substitution note if only a generic
    # product gets matched.
    generic_fallback_name: str | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> ParsedIngredient:
        """Builds a ParsedIngredient defensively — missing/odd fields fall
        back to sane defaults rather than raising, since the LLM's output
        shape can drift."""
        diy_raw = raw.get("diy_substitute") or None
        return cls(
            name_en=str(raw.get("name_en") or "item"),
            search_terms=[str(t) for t in (raw.get("search_terms") or [])] or [str(raw.get("name_en") or "item")],
            category_hint=str(raw.get("category_hint") or "other"),
            quantity=_safe_float(raw.get("quantity"), default=1.0),
            quantity_unit=str(raw.get("quantity_unit") or "pcs"),
            quantity_stated=bool(raw.get("quantity_stated", False)),
            essential=bool(raw.get("essential", True)),
            substitute_hint=raw.get("substitute_hint") or None,
            diy_substitute=[SubstituteComponent.from_dict(c) for c in diy_raw] if diy_raw else None,
            is_specific_variant=bool(raw.get("is_specific_variant", False)),
            generic_fallback_name=raw.get("generic_fallback_name") or None,
        )


@dataclass
class MatchComponent:
    """One real product matched for a DIY substitute component — see
    Match.components. quantity/line_total mirror Match's own fields but
    scoped to just this component (a pack-size fit against its own need,
    not the original missing ingredient's)."""

    product: Product
    quantity: float
    line_total: float


@dataclass
class Match:
    """Result of matching one ingredient to the catalog."""

    product: Product | None
    status: str  # ok | substituted_brand | substituted_functional | substituted_diy | skipped_optional | unavailable_essential | unmatched | error | needs_clarification
    quantity: float = 0.0
    line_total: float = 0.0
    note: str | None = None
    # Only set for status="needs_clarification" — the distinct pack-size
    # options the customer can pick from (see find_pack_size_options).
    candidates: list[Product] | None = None
    # Only set for status="substituted_diy" — the real products standing in
    # for a single unavailable ingredient (product is None in that case;
    # line_total is the sum of these). See agent/stock.py's Tier 4.
    components: list[MatchComponent] | None = None


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
    """Fallback fuzzy match (rapidfuzz token_sort_ratio > threshold) used
    only when exact substring matching finds nothing.

    Deliberately NOT partial_ratio: it scores on the best-aligned
    substring window, so a short term that merely shares one common word
    with a long, otherwise-unrelated product name scores deceptively
    high — e.g. "fish roe" against "Koi Fish Process Cultured" scored
    87.5 (past the old 85 threshold) purely because both contain "fish";
    the rest of "roe" vs. "process cultured" never factored in, so
    caviar silently matched an ornamental pond fish. token_sort_ratio
    compares the full strings (word order normalized), which scores that
    same pair at ~33 — correctly rejecting it — while still scoring a
    genuine near-miss like "chinigura rice" against "ACI Chinigura Rice
    1kg" at ~78, well clear of the lowered 70 threshold this scorer
    needs (its "genuinely similar" scores run lower than partial_ratio's
    did, since it isn't grading on the single best-matching window)."""
    terms_lower = [t.lower() for t in search_terms if t]
    if not terms_lower:
        return []

    scored: list[tuple[float, Product]] = []
    for p in pool:
        name_lower = p.name_en.lower()
        best_ratio = max(fuzz.token_sort_ratio(term, name_lower) for term in terms_lower)
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


def _apply_specific_variant_check(ingredient: ParsedIngredient, match: Match) -> Match:
    """A clean "ok" match can still be dishonest: the scoring cascade only
    checks term overlap, so "wagyu beef" and "beef" score identically
    against an ordinary beef product — nothing in that path knows wagyu
    is a specific, almost certainly-uncarried premium variant, not just
    another word for beef. When the LLM has flagged the ingredient as
    exactly that kind of specific/premium variant, checks whether the
    matched product's name actually contains that specific descriptor;
    if not, this was really a silent downgrade to the generic version,
    so it's rewritten to look like any other functional substitution
    (same status/tone as ghee -> soybean oil) instead of quietly
    reporting success for something the customer didn't actually get.
    Only acts on a plain "ok" match — anything already flagged as a
    substitution (brand/functional/DIY) already tells the customer it
    isn't the exact original, so there's nothing dishonest to correct."""
    if match.status != "ok" or match.product is None or not ingredient.is_specific_variant:
        return match
    if ingredient.name_en.lower() in match.product.name_en.lower():
        return match  # genuinely matched the specific variant itself
    generic = ingredient.generic_fallback_name or "a regular version"
    return Match(
        product=match.product,
        status="substituted_functional",
        quantity=match.quantity,
        line_total=match.line_total,
        note=f"Couldn't find {ingredient.name_en} specifically — added {match.product.name_en} ({generic}) instead (quality and flavor will differ)",
    )


def _retrieve_scored(
    ingredient: ParsedIngredient,
    pool: list[Product],
    query_embedding: list[float] | None,
    query_embedding_model: str | None,
    query_text: str | None,
) -> list[tuple[int, Product]]:
    """Runs the retrieval cascade (embedding primary, exact/fuzzy
    fallback) against `pool` and returns (score, product) pairs, or an
    empty list if nothing was found. Factored out of match_product() so
    it can be tried twice — once against the category-hinted pool, once
    against the full catalog if that comes up empty — see
    match_product()'s category_hint fallback for why."""
    scored: list[tuple[int, Product]] = []
    if ENABLE_EMBEDDING_MATCH and query_embedding is not None and query_embedding_model is not None and query_text is not None:
        from agent.embedding_match import embedding_candidates

        embed_candidates = embedding_candidates(
            query_embedding, query_embedding_model, query_text, pool, ingredient.name_en
        )
        if embed_candidates:
            scored = [(0, p) for p in embed_candidates]

    if not scored and ENABLE_EXACT_FUZZY_MATCH:
        scored = score_candidates(pool, ingredient.search_terms, primary_term=ingredient.name_en)
        if not scored:
            fuzzy_candidates = fuzzy_match(pool, ingredient.search_terms)
            scored = [(0, p) for p in fuzzy_candidates]
            scored.sort(key=lambda pair: (-pair[0], pair[1].id))

    return scored


def match_product(
    ingredient: ParsedIngredient,
    catalog: list[Product],
    query_embedding: list[float] | None = None,
    query_embedding_model: str | None = None,
    query_text: str | None = None,
) -> Match:
    """Matches one ingredient to a real catalog product, deterministically.

    Cascade: category filter -> exact term scoring -> fuzzy fallback (+
    embedding retrieval, see below) -> best top-tier candidate (sized to
    fit) -> three-tier substitution.

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

    query_embedding/query_embedding_model (optional, precomputed by
    pipeline.py's run_agent when ENABLE_EMBEDDING_MATCH is on): a Layer-1
    addition, purely widening the candidate net alongside fuzzy_match for
    genuine vocabulary mismatches (e.g. "chickpea flour" vs. the catalog's
    "BPM Gram Flour 500gm" — zero shared substring, well under
    fuzzy_match's threshold, but obviously the same thing). Every decision
    below this point (stock, price, size fit, substitution tiers) is the
    same regardless of which tier a candidate came from — this only ever
    adds candidates, never removes or reprioritizes ones exact/fuzzy
    already found. query_embedding_model travels with the vector because
    Gemini API-key/model rotation (core/gemini_client.py) can mean this
    particular query was embedded with a different model than most of the
    catalog — embedding_candidates() only ever compares same-model vectors,
    see agent/embedding_match.py. query_text is the same query in plain
    text, needed separately because embedding_candidates() reranks its
    cosine-similarity shortlist with a cross-encoder (core/jina_client.py)
    that reasons over query and candidate text together, not just two
    independently-computed vectors. The reranker's own top pick still
    goes through one more check — an LLM verifies/selects among its top
    few candidates — before embedding_candidates() returns anything:
    live testing showed the reranker can be just as confident about a
    forced-but-wrong pick as a genuinely correct one (see
    agent/embedding_match.py's module docstring), so score/margin alone
    isn't a safe accept/reject signal on its own. When query_embedding is
    None (the default — no config change needed to keep today's exact
    behavior), this is a no-op and the cascade is byte-for-byte
    unchanged."""
    category_pool = [p for p in catalog if p.category == ingredient.category_hint]
    scored = _retrieve_scored(
        ingredient, category_pool or catalog, query_embedding, query_embedding_model, query_text
    )

    # category_hint is an LLM guess made in the same single parsing call
    # as everything else, before any catalog lookup — it's pattern-
    # matched from general grocery-taxonomy knowledge, not grounded in
    # this specific catalog's own (sometimes idiosyncratic) scheme. Live
    # auditing found it wrong on a real, non-trivial fraction of terms
    # (ketchup guessed "Salt And Sugar" instead of "Sauces And Pickles";
    # olive oil guessed "Soybean Oil" instead of its own "Olive Oil"
    # category; the same ingredient can even get a different guess
    # between calls depending on phrasing — see PROJECT_CONTEXT.md). A
    # wrong guess used to permanently hide the real product: category
    # filtering happened before retrieval, so nothing outside the
    # (wrong) guessed category was ever even considered. If the guessed
    # category's pool has nothing for it, retry once against the whole
    # catalog before giving up — cheap (every retrieval tier here
    # already scales fine to the full ~2,807-product catalog) and closes
    # this failure mode without needing category_hint to be reliable.
    if not scored and category_pool:
        scored = _retrieve_scored(ingredient, catalog, query_embedding, query_embedding_model, query_text)

    if not scored:
        if not ingredient.essential:
            return Match(
                product=None,
                status="skipped_optional",
                note=f"Couldn't find {ingredient.name_en} in our catalog — it's optional for this dish, so I skipped it",
            )
        # Nothing in the catalog even loosely resembles this ingredient
        # (as opposed to "found it, but every match is out of stock" below)
        # — still worth trying a DIY substitute before giving up, since
        # that's exactly the case for something like heavy cream, which
        # isn't carried at all, not just out of stock.
        from agent.stock import match_diy_substitute  # local import breaks the circular dependency

        diy_match = match_diy_substitute(ingredient, catalog)
        if diy_match:
            return diy_match
        # Same real-world situation as find_substitute()'s final fallback
        # below (essential, nothing worked) — use the same status so it
        # gets the same clear "couldn't fulfil" treatment in the UI,
        # rather than the weaker, more ambiguous-sounding "not found" a
        # customer could easily misread as a search/typo problem instead
        # of "we genuinely don't carry this and have no substitute."
        return Match(
            product=None,
            status="unavailable_essential",
            note=f"Sorry, we don't carry {ingredient.name_en} and couldn't find a substitute — you may need to source it elsewhere for this dish.",
        )

    top_score = scored[0][0]
    top_tier = [p for score, p in scored if score == top_score]

    in_stock_top = [p for p in top_tier if p.stock_qty > 0]
    oos_top = [p for p in top_tier if p.stock_qty == 0]

    if in_stock_top and not oos_top:
        product, qty = best_size_fit(in_stock_top, ingredient)
        return _apply_specific_variant_check(
            ingredient,
            Match(product=product, status="ok", quantity=qty, line_total=round(product.price_bdt * qty, 2)),
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

    return find_substitute(ingredient, top_tier, catalog, query_embedding, query_embedding_model, query_text)
