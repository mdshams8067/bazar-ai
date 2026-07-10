"""
agent/stock.py — Substitution tiers when every matched candidate for an
ingredient is out of stock.

Tier 1 (brand):       same category + same search terms, different product, in stock.
Tier 2 (functional):  LLM's substitute_hint searched as its own term, in stock.
Tier 3 (DIY):         essential only — LLM's diy_substitute recipe, every
                       component matched against the real catalog.
Tier 4 (skip/flag):   no substitute -> skip if optional, flag if essential.
"""
from __future__ import annotations

import logging

from agent.matcher import (
    Match,
    MatchComponent,
    ParsedIngredient,
    best_size_fit,
    fuzzy_match,
    match_product,
    score_candidates,
)
from models.product import Product

logger = logging.getLogger(__name__)


def match_diy_substitute(ingredient: ParsedIngredient, catalog: list[Product]) -> Match | None:
    """Tier 3: if the LLM proposed a DIY substitute recipe for this
    essential, unavailable ingredient, try to match every component
    against a real, in-stock catalog product. Requires ALL components to
    match cleanly (plain "ok" or "substituted_brand" — never a further
    substitution or an unmatched one): a partial substitute, e.g. finding
    butter but not milk, doesn't actually let the customer make the
    substitute, so that's treated as no substitute at all rather than
    silently adding half a recipe. Returns None (not a Match) when there's
    nothing to propose or the recipe doesn't fully pan out, so the caller
    falls through to the honest unavailable_essential flag."""
    if not ingredient.diy_substitute:
        return None

    components: list[MatchComponent] = []
    descriptions: list[str] = []
    for comp in ingredient.diy_substitute:
        comp_ingredient = ParsedIngredient(
            name_en=comp.name_en,
            search_terms=comp.search_terms,
            category_hint=comp.category_hint,
            quantity=comp.quantity,
            quantity_unit=comp.quantity_unit,
            essential=True,
        )
        comp_match = match_product(comp_ingredient, catalog)
        if comp_match.product is None or comp_match.status not in ("ok", "substituted_brand"):
            logger.info(
                f"[stock] DIY substitute for {ingredient.name_en} abandoned — "
                f"component {comp.name_en} not available"
            )
            return None
        components.append(
            MatchComponent(product=comp_match.product, quantity=comp_match.quantity, line_total=comp_match.line_total)
        )
        descriptions.append(f"{comp_match.product.name_en} (x{comp_match.quantity:g})")

    total = round(sum(c.line_total for c in components), 2)
    logger.info(f"[stock] DIY substitute for {ingredient.name_en}: {', '.join(descriptions)}")
    return Match(
        product=None,
        status="substituted_diy",
        quantity=0.0,
        line_total=total,
        note=f"{ingredient.name_en} is unavailable — added {', '.join(descriptions)} so you can make a substitute at home (results will differ from the real thing)",
        components=components,
    )


def same_category_in_stock(
    ingredient: ParsedIngredient, catalog: list[Product], exclude: list[Product]
) -> list[Product]:
    """In-stock products in the ingredient's category matching its search
    terms, excluding the already-tried (out-of-stock) candidates. Used for
    tier-1 brand substitution — e.g. ACI Chinigura Rice (out) -> Chashi
    Chinigura Rice (in stock)."""
    excluded_ids = {p.id for p in exclude}
    pool = [p for p in catalog if p.category == ingredient.category_hint and p.id not in excluded_ids]

    scored = score_candidates(pool, ingredient.search_terms, primary_term=ingredient.name_en)
    if not scored:
        scored = [(0, p) for p in fuzzy_match(pool, ingredient.search_terms)]

    return [p for _, p in scored if p.stock_qty > 0]


def search_category_in_stock(term: str, catalog: list[Product]) -> list[Product]:
    """In-stock products whose name or category contains `term` (a
    substitute_hint like "soybean oil"). Used for tier-2 functional
    substitution."""
    term_lower = term.lower()
    matches = [
        p
        for p in catalog
        if p.stock_qty > 0 and (term_lower in p.name_en.lower() or term_lower in p.category.lower())
    ]
    matches.sort(key=lambda p: p.price_bdt)
    return matches


def find_substitute(
    ingredient: ParsedIngredient, oos_candidates: list[Product], catalog: list[Product]
) -> Match:
    """Runs the substitution tiers in order for an ingredient whose every
    matched candidate is out of stock."""
    oos_name = oos_candidates[0].name_en if oos_candidates else ingredient.name_en

    # TIER 1 — brand substitution.
    brand_candidates = same_category_in_stock(ingredient, catalog, exclude=oos_candidates)
    if brand_candidates:
        product, qty = best_size_fit(brand_candidates, ingredient)
        logger.info(f"[stock] brand substitution: {oos_name} -> {product.name_en}")
        return Match(
            product=product,
            status="substituted_brand",
            quantity=qty,
            line_total=round(product.price_bdt * qty, 2),
            note=f"{oos_name} is out of stock — added {product.name_en} instead",
        )

    # TIER 2 — functional substitution via the LLM's substitute_hint.
    if ingredient.substitute_hint:
        func_candidates = search_category_in_stock(ingredient.substitute_hint, catalog)
        if func_candidates:
            product, qty = best_size_fit(func_candidates, ingredient)
            logger.info(f"[stock] functional substitution: {ingredient.name_en} -> {product.name_en}")
            return Match(
                product=product,
                status="substituted_functional",
                quantity=qty,
                line_total=round(product.price_bdt * qty, 2),
                note=f"{ingredient.name_en} is unavailable — added {product.name_en} as a cooking substitute (flavor may differ)",
            )

    # TIER 3 — skip if optional; if essential, try a DIY substitute recipe
    # before giving up.
    if not ingredient.essential:
        logger.info(f"[stock] skipping optional out-of-stock ingredient: {ingredient.name_en}")
        return Match(
            product=None,
            status="skipped_optional",
            note=f"{ingredient.name_en} is out of stock — it's optional for this dish, so I skipped it",
        )

    diy_match = match_diy_substitute(ingredient, catalog)
    if diy_match:
        return diy_match

    # TIER 4 — no substitute of any kind: honest flag.
    logger.info(f"[stock] essential ingredient unavailable: {ingredient.name_en}")
    return Match(
        product=None,
        status="unavailable_essential",
        note=f"Sorry, {ingredient.name_en} is out of stock right now and no substitute worked — you may want to check back later or source it elsewhere.",
    )
