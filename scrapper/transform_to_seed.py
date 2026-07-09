#!/usr/bin/env python3
"""
Transform Scraped Products to Seed Data
=========================================
Reads data/products_scraped.json and outputs data/seed_data.json
matching the schema:
  (id, name_en, name_bn, category, price_bdt, unit, unit_value,
   stock_qty, image_url)

Rules:
  - name_bn is null (Bangla names not scraped yet)
  - unit / unit_value are parsed out of the product name via regex
    (falling back to the scraper's raw `unit` field, then "pcs")
  - stock_qty: seeded random 5-50, with demo overrides layered on top
    (see OUT_OF_STOCK_EXACT / OUT_OF_STOCK_PATTERNS / FRESH_STOCK_RANGE
    below)
"""

import json
import random
import re
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

INPUT_FILE = Path("data/products_scraped.json")
OUTPUT_FILE = Path("data/seed_data.json")

RANDOM_SEED = 42
BASE_STOCK_RANGE = (5, 50)
FRESH_STOCK_RANGE = (10, 30)  # Meat & Fish

FRESH_CATEGORIES = {"Meat", "Fish"}

# TIER 1 — exact-name overrides for the rice substitution demo
EXACT_STOCK_OVERRIDES = {
    "ACI Pure Chinigura Rice 1kg": 0,
    "ACI Aroma Chinigura Rice 1kg": 0,
    "Rupchanda Chinigura Rice 1kg": 0,
    "Chashi Chinigura Rice 1kg": 20,
    "Chashi Chinigura Rice 2kg": 12,
    # REALISM — one everyday item with a natural size-substitution gap
    "Rupchanda Soyabean Oil 1Ltr.": 0,
}

# TIER 2 / TIER 3 — substring patterns forced to stock 0 (case-insensitive)
# NOTE: "ghee" uses word boundaries so it doesn't false-positive on
# "Gheebhog" (an aromatic rice, not ghee). "raisin" is intentionally left
# boundary-free on the right so it still matches the plural "Raisins".
OUT_OF_STOCK_PATTERNS = [
    r"\bghee\b",
    r"kismis",
    r"raisin",
    r"kishmish",
    r"কিশমিশ",
    r"ঘি",
]

# =============================================================================
# UNIT EXTRACTION
# =============================================================================

_UNIT_ALIASES = {
    "ltr": "ltr", "l": "ltr",
    "ml": "ml",
    "kg": "kg",
    "gm": "gm", "g": "gm",
}


def _norm_unit(token: str) -> str:
    return _UNIT_ALIASES[token.lower()]


NUM = r"\d+(?:\.\d+)?"
UNIT_TOK = r"(ltr|ml|kg|gm|g)"

# Tier 1: weight/volume patterns (kg/gm/ltr/ml) — these represent the actual
# package size and always win when present, e.g. "300gm (14-15)Pcs" should
# report unit=gm/300, not unit=pcs/14.
WEIGHT_VOLUME_PATTERNS = [
    # "(500-599 gm)" / "(1.2 -2.499 kg)" -> lower bound
    (re.compile(rf"\(\s*({NUM})\s*-\s*{NUM}\s*{UNIT_TOK}\s*\)", re.IGNORECASE),
     lambda m: (_norm_unit(m.group(2)), float(m.group(1)))),

    # "55gm+/pcs" -> gm (weight per piece)
    (re.compile(rf"({NUM})\s*gm\+/pcs", re.IGNORECASE),
     lambda m: ("gm", float(m.group(1)))),

    # "900(±)100gm" / "20(±)2gm" / "27.5(±)1gm" -> base value before tolerance
    (re.compile(rf"({NUM})\s*\(\s*\xb1\s*\)\s*{NUM}\s*{UNIT_TOK}\b", re.IGNORECASE),
     lambda m: (_norm_unit(m.group(2)), float(m.group(1)))),

    # "400gm+" / "2kg+" -> value before the trailing '+'
    (re.compile(rf"({NUM})\s*{UNIT_TOK}\+", re.IGNORECASE),
     lambda m: (_norm_unit(m.group(2)), float(m.group(1)))),

    # Plain "5Ltr." / "500ml" / "1kg" / "100gm"
    (re.compile(rf"({NUM})\s*{UNIT_TOK}\b", re.IGNORECASE),
     lambda m: (_norm_unit(m.group(2)), float(m.group(1)))),

    # "(Kg)" bare parenthesized unit -> 1 unit
    (re.compile(rf"\(\s*{UNIT_TOK}\s*\)", re.IGNORECASE),
     lambda m: (_norm_unit(m.group(1)), 1.0)),

    # "Loose kg" / trailing bare "Kg" word
    (re.compile(r"\bLoose\s+kg\b", re.IGNORECASE),
     lambda m: ("kg", 1.0)),
    (re.compile(r"\bkg\b\s*$", re.IGNORECASE),
     lambda m: ("kg", 1.0)),
]

# Tier 2: pure piece-count patterns — only consulted when no weight/volume
# unit was found anywhere in the name (e.g. plain egg/fish piece counts).
COUNT_PATTERNS = [
    # "(30-40 Pcs/kg)" -> pcs/kg, lower bound
    (re.compile(rf"\(\s*({NUM})\s*-\s*{NUM}\s*Pcs\s*/\s*kg\s*\)", re.IGNORECASE),
     lambda m: ("pcs/kg", float(m.group(1)))),

    # "(14-15)Pcs" -> pcs, lower bound
    (re.compile(rf"\(\s*({NUM})\s*-\s*{NUM}\s*\)\s*Pcs\b", re.IGNORECASE),
     lambda m: ("pcs", float(m.group(1)))),

    # "12Pcs" -> pcs
    (re.compile(rf"({NUM})\s*Pcs\b", re.IGNORECASE),
     lambda m: ("pcs", float(m.group(1)))),

    # bare trailing "Pcs" with no count
    (re.compile(r"\bPcs\b", re.IGNORECASE),
     lambda m: ("pcs", 1.0)),
]

UNIT_PATTERNS = WEIGHT_VOLUME_PATTERNS + COUNT_PATTERNS


def _first_match(text: str, patterns) -> tuple[str, float] | None:
    for pattern, handler in patterns:
        match = pattern.search(text)
        if match:
            return handler(match)
    return None


def extract_unit(name: str, raw_unit: str | None) -> tuple[str, float]:
    """Extract (unit, unit_value) from a product name. Weight/volume units
    (kg/gm/ltr/ml) always take priority over pure piece counts. Falls back
    to the scraper's raw unit field, then to a flat "pcs" default."""
    for source in (name, raw_unit if raw_unit and "image square attribute" not in raw_unit else None):
        if not source:
            continue
        result = _first_match(source, WEIGHT_VOLUME_PATTERNS)
        if result:
            return result

    for source in (name, raw_unit if raw_unit and "image square attribute" not in raw_unit else None):
        if not source:
            continue
        result = _first_match(source, COUNT_PATTERNS)
        if result:
            return result

    return "pcs", 1.0


# =============================================================================
# STOCK ASSIGNMENT
# =============================================================================


def is_forced_out_of_stock(name: str) -> bool:
    name_lower = name.lower()
    return any(re.search(p, name_lower, re.IGNORECASE) for p in OUT_OF_STOCK_PATTERNS)


def assign_stock(name: str, category: str, rng: random.Random) -> int:
    if name in EXACT_STOCK_OVERRIDES:
        return EXACT_STOCK_OVERRIDES[name]

    if is_forced_out_of_stock(name):
        return 0

    if category in FRESH_CATEGORIES:
        return rng.randint(*FRESH_STOCK_RANGE)

    return rng.randint(*BASE_STOCK_RANGE)


# =============================================================================
# MAIN TRANSFORM
# =============================================================================


def transform():
    if not INPUT_FILE.exists():
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        print("Run scraper.py first to generate product data.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        products = json.load(f)

    print(f"Loaded {len(products)} scraped products")

    before_counts: dict[str, int] = {}
    for p in products:
        cat = (p.get("category") or "Uncategorized").strip()
        before_counts[cat] = before_counts.get(cat, 0) + 1

    rng = random.Random(RANDOM_SEED)

    seed_data = []
    dropped = []
    unit_fallback_count = 0

    for product in products:
        name_en = (product.get("name") or "").strip()
        if not name_en:
            dropped.append(product)
            continue

        category = (product.get("category") or "Uncategorized").strip()
        unit, unit_value = extract_unit(name_en, product.get("unit"))
        if unit == "pcs" and unit_value == 1.0:
            # Only count as a genuine fallback when nothing in the name matched
            if not any(p.search(name_en) for p, _ in UNIT_PATTERNS):
                unit_fallback_count += 1

        stock_qty = assign_stock(name_en, category, rng)

        seed_data.append({
            "id": len(seed_data) + 1,
            "name_en": name_en,
            "name_bn": None,
            "category": category,
            "price_bdt": product.get("price_bdt"),
            "unit": unit,
            "unit_value": unit_value,
            "stock_qty": stock_qty,
            "image_url": product.get("image_url"),
        })

    after_counts: dict[str, int] = {}
    for row in seed_data:
        after_counts[row["category"]] = after_counts.get(row["category"], 0) + 1

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(seed_data, f, ensure_ascii=False, indent=2)

    # =========================================================================
    # SANITY REPORT
    # =========================================================================
    print("\n" + "=" * 60)
    print("PER-CATEGORY BEFORE/AFTER COMPARISON")
    print("=" * 60)
    all_cats = sorted(set(before_counts) | set(after_counts), key=lambda c: -before_counts.get(c, 0))
    ok = True
    for cat in all_cats:
        b = before_counts.get(cat, 0)
        a = after_counts.get(cat, 0)
        flag = "OK" if b == a else "MISMATCH"
        if b != a:
            ok = False
        print(f"  {cat:25s} before={b:4d}  after={a:4d}  [{flag}]")
    print(f"\n  Dropped rows (no name): {len(dropped)}")
    print(f"  Total: {'ALL PRODUCTS CARRIED THROUGH' if ok and not dropped else 'MISMATCH DETECTED'}")

    print("\n" + "=" * 60)
    print("SANITY REPORT")
    print("=" * 60)
    print(f"  Input products:  {len(products)}")
    print(f"  Output products: {len(seed_data)}")
    assert len(products) == 2807, "unexpected input size"
    assert len(seed_data) == 2807, "unexpected output size"

    print("\n  Final category counts:")
    for cat, count in sorted(after_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat:25s} {count:4d}")

    print("\n  In-stock broiler chicken products (>=3 required):")
    broiler = [r for r in seed_data if "broiler" in r["name_en"].lower() and r["stock_qty"] > 0]
    for r in broiler[:6]:
        print(f"    • {r['name_en']} -> stock {r['stock_qty']}")
    assert len(broiler) >= 3, "expected at least 3 in-stock broiler chicken products"

    print("\n  Rice check (Chinigura):")
    for name in ["ACI Pure Chinigura Rice 1kg", "ACI Aroma Chinigura Rice 1kg", "Rupchanda Chinigura Rice 1kg"]:
        row = next(r for r in seed_data if r["name_en"] == name)
        print(f"    • {row['name_en']} -> stock {row['stock_qty']} (expect 0)")
        assert row["stock_qty"] == 0
    chashi1 = next(r for r in seed_data if r["name_en"] == "Chashi Chinigura Rice 1kg")
    chashi2 = next(r for r in seed_data if r["name_en"] == "Chashi Chinigura Rice 2kg")
    print(f"    • {chashi1['name_en']} -> stock {chashi1['stock_qty']} (expect 20, substitute target)")
    print(f"    • {chashi2['name_en']} -> stock {chashi2['stock_qty']} (expect 12)")
    assert chashi1["stock_qty"] == 20 and chashi2["stock_qty"] == 12

    print("\n  Ghee check:")
    ghee_rows = [r for r in seed_data if re.search(r"\bghee\b", r["name_en"], re.IGNORECASE)]
    ghee_in_stock = [r for r in ghee_rows if r["stock_qty"] != 0]
    print(f"    Total ghee-matching products: {len(ghee_rows)}, all at stock 0: {len(ghee_in_stock) == 0}")
    non_ghee_gheebhog = [r for r in seed_data if "gheebhog" in r["name_en"].lower()]
    for r in non_ghee_gheebhog:
        print(f"    • (excluded, not real ghee) {r['name_en']} -> stock {r['stock_qty']}")
    assert not ghee_in_stock
    soy_in_stock = [r for r in seed_data if r["category"] == "Soybean Oil" and r["stock_qty"] > 0]
    print(f"    In-stock soyabean oil substitutes ({len(soy_in_stock)}):")
    for r in soy_in_stock:
        print(f"    • {r['name_en']} -> stock {r['stock_qty']}")
    assert len(soy_in_stock) >= 3, "expected at least 3 in-stock soyabean oil products"

    print("\n  Kismis/Raisin check:")
    kismis_rows = [r for r in seed_data if re.search(r"kismis|raisin", r["name_en"], re.IGNORECASE)]
    kismis_in_stock = [r for r in kismis_rows if r["stock_qty"] != 0]
    for r in kismis_rows:
        print(f"    • {r['name_en']} -> stock {r['stock_qty']}")
    print(f"    All at stock 0: {len(kismis_in_stock) == 0}")
    assert not kismis_in_stock

    print("\n  Soyabean oil size-substitution check:")
    r1 = next(r for r in seed_data if r["name_en"] == "Rupchanda Soyabean Oil 1Ltr.")
    r2 = next(r for r in seed_data if r["name_en"] == "Rupchanda Soyabean Oil 2Ltr.")
    r5 = next(r for r in seed_data if r["name_en"] == "Rupchanda Soyabean Oil 5Ltr.")
    print(f"    • {r1['name_en']} -> stock {r1['stock_qty']} (expect 0)")
    print(f"    • {r2['name_en']} -> stock {r2['stock_qty']} (expect >0)")
    print(f"    • {r5['name_en']} -> stock {r5['stock_qty']} (expect >0)")
    assert r1["stock_qty"] == 0 and r2["stock_qty"] > 0 and r5["stock_qty"] > 0

    print("\n  Units:")
    print(f"    Successfully extracted from name/raw unit: {len(seed_data) - unit_fallback_count}")
    print(f"    Fallback to default 'pcs' (1.0): {unit_fallback_count}")

    print("\n  Meat/Fish freshness check:")
    meat_rows = [r for r in seed_data if r["category"] == "Meat"]
    fish_rows = [r for r in seed_data if r["category"] == "Fish"]
    print(f"    Meat: {len(meat_rows)} rows, all stock in [10,30]: "
          f"{all(10 <= r['stock_qty'] <= 30 for r in meat_rows)}")
    print(f"    Fish: {len(fish_rows)} rows, all stock in [10,30]: "
          f"{all(10 <= r['stock_qty'] <= 30 for r in fish_rows)}")

    print("\n" + "=" * 60)
    print(f"  Output written to: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    transform()
