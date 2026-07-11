"""
seed/enrich_labels.py — One-off batch job: generates a synonym-aware,
noise-stripped text representation of every product's name_en, stored in
Product.embedding_source_text, for the optional Layer 1 embedding-retrieval
addition to actually embed instead of the raw catalog label.

Why this exists: a raw scraped name like "Farm Fresh Ghee 900(±)100gm Tin"
is mostly noise relative to what the product actually *is* — brand, pack
size, container type all dilute the concept an embedding needs to
recognize "clarified butter" as the same thing as "ghee". Verified live
this session that embedding the raw label directly is why several genuine
synonym pairs (ghee/clarified butter, brinjal/eggplant, icing sugar/
powdered sugar) scored far lower than they should have.

The prompt below isn't generic — it's shaped by actually querying the
catalog first (see PROJECT_CONTEXT.md):
- `name_bn` is null for all 2,807 products (no structured Bangla data
  exists), but 885/2,807 (32%) already carry a "Banglish (English)" gloss
  baked into name_en by the scraper itself (e.g. "Dhoniapata (Coriander
  Leaf)", "Begun Shobuj (Brinjal Round Green)") — those need their
  existing Banglish term preserved and expanded, not silently dropped.
  The other 68% (almost entirely branded/packaged goods) have zero
  Bangla trace at all and need synonyms generated from the LLM's own
  knowledge instead.
- A real, dangerous trap verified in this exact catalog: an ingredient
  word appearing in a name doesn't always mean the product IS that
  ingredient. "Akij Essential Katari Gheebhog 5kg" is category=Rice (a
  rice variety name, nothing to do with ghee); five separate "Ghee
  Toast/Bite Biscuit" products are category=Snacks; "Truffle Chocolate"
  and "Honey Lemon Candy" are category=Candy Chocolate; "Duck Masala" is
  category=Ready Mix (a spice packet, not duck meat) — the exact same
  "named after an ingredient, isn't that ingredient" trap already found
  live via the reranker tests (truffle-flavored candy, honey-flavored
  candy, Duck Masala spice mix). Naively enriching these with the
  ingredient's own synonyms would actively make the index worse — a
  "ghee" search could then match a biscuit. The prompt passes each
  product's real `category` alongside its name specifically so the LLM
  can use it as ground truth to catch this.

Uses the existing Gemini chat infrastructure (core/llm.py — same
rotation/fallback already built for the main agent), not a new provider,
since this is a text-generation task, not embedding/reranking.

Run as a script: `python -m seed.enrich_labels` from backend/ (venv active).
"""
import json
import logging
import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core import llm
from core.config import DATABASE_URL
from models.product import Product

logger = logging.getLogger(__name__)

# Kept small: a large batch risks the LLM dropping/merging entries under
# its own output-token budget, and a partial-batch failure loses less
# progress. ~35 products x a short instruction each comfortably fits one
# call's output budget without truncation risk.
_BATCH_SIZE = 35
_MAX_OUTPUT_TOKENS = 3072

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_SYSTEM_PROMPT = """You are building a product search index for a Bangladeshi grocery app (Bazar AI). \
Shoppers search in English, Banglish (Bangla words spelled in Latin letters), or a mix of both.

For each product, you're given its name AND its real catalog category — use the category as \
ground truth for what kind of product this actually is. Output the core concept plus common \
alternate names, stripped of brand names, pack sizes, container types, and promotional text \
("(±)100gm", "Tin", "Packet", country-of-origin suffixes, etc. all get dropped).

CRITICAL — an ingredient word appearing in a product's name does NOT always mean the product IS \
that ingredient. Check the category first:
- "Akij Essential Katari Gheebhog 5kg" — category Rice. This is a rice variety, NOT ghee, despite \
  containing the word "Ghee". Describe it as rice.
- "Paragon Ghee Toast Biscuit 200gm" — category Snacks. This is a biscuit flavored/named after \
  ghee, NOT ghee itself. Describe it as a biscuit/snack, optionally noting the ghee flavor.
- "It's Better Truffle Chocolate" / "Halls Honey Lemon Candy" — category Candy Chocolate. These \
  are candy, not truffle mushroom or honey. Describe them as candy.
- "Haiko Duck Masala" — category Ready Mix. This is a spice/seasoning packet, NOT duck meat. \
  Describe it as a spice mix.
If the category matches the literal ingredient (e.g. an actual ghee product IS category Dairy or \
similar, actual duck meat IS category Meat), then yes, treat it as that ingredient normally.

For genuine ingredients/foods (category matches what the name says), cover THREE kinds of \
alternates, whichever genuinely apply — don't force one that doesn't fit:
1. English synonyms, including US/UK variants where they differ (eggplant/brinjal/aubergine, \
capsicum/bell pepper, icing sugar/powdered sugar/confectioner's sugar, clarified butter/ghee).
2. Spelling variants actually used inconsistently in this catalog (e.g. "soyabean" alongside the \
standard spelling "soybean" — both should appear).
3. The common Banglish term for this item, if one exists — whether or not the input name already \
has one. If the input name already includes a parenthetical Bangla/Banglish gloss (e.g. "Begun \
Shobuj (Brinjal Round Green)" — "Begun" is the Banglish term), KEEP that exact term in your \
output, don't drop it, and add further synonyms around it. If the input is a purely branded/ \
English name with no existing gloss, supply the common Banglish term yourself if a Bangladeshi \
shopper would plausibly search that way (e.g. rice is also "chal", onion is also "piyaj"). Skip \
this if you don't actually know a real term — never invent one.

Return ONLY a JSON object: {"items": [{"id": <int>, "text": "<space-separated concept + \
synonyms, lowercase, no punctuation>"}, ...]} — one entry per product, in the same order given, \
same id. No markdown fences, no commentary.

Examples (illustrative, not exhaustive):
Input: {"id": 501, "name": "Farm Fresh Ghee 900(±)100gm Tin", "category": "Dairy"}
Output: {"id": 501, "text": "ghee clarified butter dairy cooking fat"}

Input: {"id": 502, "name": "Begun Shobuj (Brinjal Round Green)", "category": "Fruits And Vegetables"}
Output: {"id": 502, "text": "begun brinjal eggplant aubergine round green"}

Input: {"id": 503, "name": "Fresh Soyabean Oil 2Ltr.", "category": "Soybean Oil"}
Output: {"id": 503, "text": "soyabean oil soybean oil cooking oil"}

Input: {"id": 504, "name": "Haiko Icing Sugar 150gm Packet", "category": "Baking Needs"}
Output: {"id": 504, "text": "icing sugar powdered sugar confectioners sugar gura chini"}

Input: {"id": 505, "name": "Paragon Ghee Toast Biscuit 200gm", "category": "Snacks"}
Output: {"id": 505, "text": "ghee toast biscuit snack cookie"}

Input: {"id": 506, "name": "Akij Essential Katari Gheebhog 5kg", "category": "Rice"}
Output: {"id": 506, "text": "gheebhog katari rice aromatic rice chal"}

Input: {"id": 507, "name": "Haiko Duck Masala 40gm", "category": "Ready Mix"}
Output: {"id": 507, "text": "duck masala spice mix seasoning curry powder"}
"""

_sync_engine = create_engine(DATABASE_URL)
_SyncSession = sessionmaker(bind=_sync_engine)


def _extract_json(text: str) -> dict:
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    return json.loads(cleaned)


def enrich(only_missing: bool = True) -> int:
    """Generates and stores embedding_source_text for every product.
    Returns row count updated.

    only_missing=True (default) skips products that already have
    enrichment text — safe to re-run after a partial run without
    re-spending LLM quota on rows that already succeeded."""
    db = _SyncSession()
    try:
        query = db.query(Product).order_by(Product.id)
        if only_missing:
            query = query.filter(Product.embedding_source_text.is_(None))
        products = query.all()

        updated = 0
        for start in range(0, len(products), _BATCH_SIZE):
            batch = products[start : start + _BATCH_SIZE]
            user_message = json.dumps(
                {"products": [{"id": p.id, "name": p.name_en, "category": p.category} for p in batch]},
                ensure_ascii=False,
            )
            raw = llm.chat(_SYSTEM_PROMPT, user_message, max_tokens=_MAX_OUTPUT_TOKENS, temperature=0.1)
            try:
                parsed = _extract_json(raw)
            except (json.JSONDecodeError, ValueError):
                logger.exception(f"[enrich_labels] JSON parse failed for batch starting at {start}, skipping")
                continue

            by_id = {item["id"]: item["text"] for item in parsed.get("items", [])}
            for product in batch:
                text = by_id.get(product.id)
                if text:
                    product.embedding_source_text = text
                    updated += 1
                else:
                    logger.warning(f"[enrich_labels] no enrichment returned for product {product.id}")
            db.commit()
            logger.info(f"Enriched {min(start + _BATCH_SIZE, len(products))}/{len(products)} products")
    finally:
        db.close()

    return updated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = enrich()
    print(f"Enriched {count} products into {_sync_engine.url}")
