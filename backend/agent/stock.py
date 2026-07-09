"""
agent/stock.py — Three-tier substitution when every matched candidate for an
ingredient is out of stock.

Tier 1 (brand):      same category + same search terms, different product, in stock.
Tier 2 (functional):  LLM's substitute_hint searched as its own term, in stock.
Tier 3 (skip/flag):  no substitute -> skip if optional, flag if essential.
"""
from __future__ import annotations

import logging

from agent.matcher import (
    Match,
    ParsedIngredient,
    best_size_fit,
    fuzzy_match,
    score_candidates,
)
from models.product import Product

logger = logging.getLogger(__name__)


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
    """Runs the three substitution tiers in order for an ingredient whose
    every matched candidate is out of stock."""
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

    # TIER 3 — graceful skip (optional) or honest flag (essential).
    if not ingredient.essential:
        logger.info(f"[stock] skipping optional out-of-stock ingredient: {ingredient.name_en}")
        return Match(
            product=None,
            status="skipped_optional",
            note=f"{ingredient.name_en} is out of stock — it's optional for this dish, so I skipped it",
        )

    logger.info(f"[stock] essential ingredient unavailable: {ingredient.name_en}")
    return Match(
        product=None,
        status="unavailable_essential",
        note=f"{ingredient.name_en} is essential but unavailable — you may want to check back later",
    )
