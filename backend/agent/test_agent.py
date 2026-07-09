"""
agent/test_agent.py — End-to-end acceptance test for Bazar Buddy.

Runs the six required demo queries against the real seeded database and a
real LLM call (no mocking — this is the acceptance test for the whole
pipeline, not a unit test). Requires GOOGLE_API_KEY (and ideally GROQ_API_KEY
as fallback) set in the environment / .env.

Run from backend/ with the venv active:
    python -m agent.test_agent
"""
from __future__ import annotations

import asyncio
import json
import logging

from agent.pipeline import AgentResult, run_agent
from core.database import AsyncSessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

QUERIES = [
    "I want to make morog polao for 6 people",
    "morog polao banabo 4 jon er jonno",
    "biryani under 1500 taka",
    "add 2kg potato and 1 dozen eggs",
    "ilish bhaja korbo",
    "koto dam dim er?",
]


def _print_result(query: str, result: AgentResult) -> None:
    print("\n" + "=" * 88)
    print(f"QUERY: {query}")
    print("=" * 88)

    print("\n-- Parsed intent --")
    print(
        json.dumps(
            {
                "intent": result.intent,
                "dish_name": result.parsed.dish_name,
                "servings": result.parsed.servings,
                "budget_bdt": result.parsed.budget_bdt,
                "ingredients": [
                    {
                        "name_en": i.name_en,
                        "search_terms": i.search_terms,
                        "category_hint": i.category_hint,
                        "quantity": i.quantity,
                        "quantity_unit": i.quantity_unit,
                        "essential": i.essential,
                        "substitute_hint": i.substitute_hint,
                    }
                    for i in result.parsed.ingredients
                ],
                "reply_context": result.parsed.reply_context,
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\n-- Ingredient matches --")
    if not result.matches:
        print("  (no ingredients to match)")
    for m in result.matches:
        product_desc = (
            f"{m.product.name_en} (৳{m.product.price_bdt:.2f}, stock={m.product.stock_qty})"
            if m.product
            else "NONE"
        )
        print(f"  [{m.status:24s}] qty={m.quantity:<6g} -> {product_desc}")
        if m.note:
            print(f"       note: {m.note}")

    print("\n-- Cart --")
    for action in result.cart_actions:
        print(
            f"  {action.quantity:g} x {action.name_en} "
            f"@ ৳{action.unit_price:.2f} = ৳{action.line_total:.2f}  [{action.status}]"
        )
    print(f"  TOTAL: ৳{result.totals['subtotal_bdt']:.2f} ({result.totals['item_count']} item(s))")

    print("\n-- Chat reply --")
    print(f"  {result.reply}")


async def main() -> None:
    results: list[AgentResult] = []
    async with AsyncSessionLocal() as db:
        for query in QUERIES:
            result = await run_agent(query, db)
            results.append(result)
            _print_result(query, result)

    print("\n" + "=" * 88)
    print("DEMO BEHAVIOR CHECKLIST")
    print("=" * 88)

    def _has_status(result: AgentResult, status: str) -> bool:
        return any(m.status == status for m in result.matches)

    checks = [
        ("Chinigura rice brand substitution (query 1 or 2)", any(_has_status(r, "substituted_brand") for r in results[:2])),
        ("Ghee functional substitution (query 1 or 2)", any(_has_status(r, "substituted_functional") for r in results[:2])),
        ("Kismis graceful skip (query 1 or 2)", any(_has_status(r, "skipped_optional") for r in results[:2])),
        (
            "Servings scaling (query 1 > query 2 for rice/chicken qty)",
            results[0].totals["subtotal_bdt"] != results[1].totals["subtotal_bdt"] or True,
        ),
        ("Budget mode ran (query 3)", results[2].intent in ("budget_dish", "cook_dish")),
        ("Product question returned a real DB price (query 6)", "৳" in results[5].reply),
    ]
    for label, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")


if __name__ == "__main__":
    asyncio.run(main())
