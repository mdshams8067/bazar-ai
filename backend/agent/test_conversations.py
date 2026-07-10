"""
agent/test_conversations.py — Multi-turn conversational acceptance suite.

agent/test_agent.py checks single-turn requests against the real LLM. It
never caught the keep_only_items or modify_dish bugs, because those only
show up across TWO turns ("add X" then "only keep X" / "make it beef") —
and specifically in how routers/chat.py mutates the real cart in response,
not just in what the LLM parses. This suite closes that gap: a fixed,
growable list of multi-turn scenarios run against the real LLM, the real
router, and a real (throwaway) user's cart — the same integration surface
a live conversation actually exercises — so a regression here shows up by
running this script, not by a person chatting until something breaks.

Each turn carries several PHRASING VARIANTS of the same request — the way
different real people would actually type it, not one canonical sentence
repeated — and --repeat runs the whole suite that many passes, cycling
through those variants each pass. This is deliberately not just "run the
same input N times": a single phrasing that happens to work is weak
evidence; the same intent surviving several different people's wording is
the actual claim being tested. (Repeating one exact phrasing across passes
would also mostly replay core/llm.py's response cache rather than sample
the LLM again — varying the wording sidesteps that for free, as long as
--repeat doesn't exceed a turn's variant count; see --repeat's help text.)

Requires GOOGLE_API_KEY (and ideally GROQ_API_KEY) set, and a seeded
catalog (the real bazar.db, not a toy fixture — these scenarios need real
products like chicken/beef/mutton/rice to match against). Works standalone,
no separately-running server needed (drives the app in-process over ASGI).

Run from backend/ with the venv active:
    python -m agent.test_conversations
    python -m agent.test_conversations --repeat 5
    python -m agent.test_conversations --repeat 5 --quiet   # summary only
"""
from __future__ import annotations

import argparse
import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from httpx import ASGITransport, AsyncClient

from main import app

CartCheck = Callable[[dict], tuple[bool, str]]


def _names(cart: dict) -> list[str]:
    return [item["product"]["name_en"].lower() for item in cart["items"]]


def contains(term: str) -> CartCheck:
    def check(cart: dict) -> tuple[bool, str]:
        found = any(term.lower() in n for n in _names(cart))
        return found, f'cart contains "{term}"'

    return check


def not_contains(term: str) -> CartCheck:
    def check(cart: dict) -> tuple[bool, str]:
        found = any(term.lower() in n for n in _names(cart))
        return not found, f'cart does not contain "{term}"'

    return check


def cart_empty() -> CartCheck:
    def check(cart: dict) -> tuple[bool, str]:
        return cart["item_count"] == 0, "cart is empty"

    return check


@dataclass
class Turn:
    # Several ways different people would phrase the same request — NOT
    # just one canonical sentence. A single string is still accepted and
    # wrapped into a one-element list, for turns where phrasing genuinely
    # doesn't vary (e.g. a fixed dish name).
    messages: list[str]
    checks: list[CartCheck] = field(default_factory=list)
    # None means "don't care" — used for the off-topic scenario, where the
    # exact fallback label matters less than "didn't crash, didn't guess".
    expected_intent: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.messages, str):
            self.messages = [self.messages]

    def pick(self, pass_index: int) -> str:
        return self.messages[pass_index % len(self.messages)]


@dataclass
class Scenario:
    name: str
    turns: list[Turn]


SCENARIOS: list[Scenario] = [
    Scenario(
        "add then remove one item",
        [
            Turn(
                ["add 2kg rice and a dozen eggs", "I need 2kg rice and a dozen eggs", "put 2kg rice and 12 eggs in my cart"],
                [contains("rice"), contains("egg")],
            ),
            Turn(
                ["remove the eggs", "take the eggs out of my cart", "actually I don't need the eggs, remove them"],
                [contains("rice"), not_contains("egg")],
                expected_intent="remove_items",
            ),
        ],
    ),
    Scenario(
        "add then clear cart entirely",
        [
            Turn(["add 1kg rice", "put 1kg of rice in my cart"], [contains("rice")]),
            Turn(
                ["clear my whole cart", "empty my cart please", "remove everything from my cart"],
                [cart_empty()],
                expected_intent="clear_cart",
            ),
        ],
    ),
    Scenario(
        "cook a dish then keep only one ingredient",
        [
            Turn(["morog polao for 4", "I want to make morog polao for 4 people"], [contains("rice"), contains("chicken")]),
            Turn(
                [
                    "only keep the rice, remove everything else",
                    "just keep the rice and get rid of the rest",
                    "remove everything except the rice",
                ],
                [contains("rice"), not_contains("chicken")],
                expected_intent="keep_only_items",
            ),
        ],
    ),
    Scenario(
        "cook a dish then swap the protein (the reported bug: 'make it beef')",
        [
            Turn(["biryani for 4", "I want to make biryani for 4 people"], [contains("chicken")]),
            Turn(
                [
                    "make it beef instead",
                    "can you swap the chicken for beef",
                    "actually, use beef not chicken",
                    "I'd prefer beef please",
                ],
                [contains("beef"), not_contains("chicken"), contains("rice")],
                expected_intent="modify_dish",
            ),
        ],
    ),
    Scenario(
        "cook a dish then swap the protein, different phrasing",
        [
            Turn(["morog polao for 6", "morog polao banabo 6 jon er jonno"], [contains("chicken")]),
            Turn(
                [
                    "use mutton instead",
                    "swap the chicken for mutton please",
                    "replace the chicken with mutton",
                    "no chicken, mutton instead",
                ],
                [contains("mutton"), not_contains("chicken"), contains("rice")],
                expected_intent="modify_dish",
            ),
        ],
    ),
    Scenario(
        '"keep only" with a nonexistent item is a safe no-op, not a wipe',
        [
            Turn(["add 1kg rice", "put 1kg rice in my cart"], [contains("rice")]),
            Turn(
                ["only keep the durian in my cart", "just keep the durian, remove the rest"],
                [contains("rice")],
                expected_intent="keep_only_items",
            ),
        ],
    ),
    Scenario(
        "off-topic message gets an honest redirect, not a crash or a guess",
        [
            Turn(
                ["what's the weather like today", "tell me a joke", "how's it going"],
                expected_intent="other",
            ),
        ],
    ),
]


@dataclass
class CheckResult:
    scenario: str
    turn_index: int
    description: str
    passed: bool
    message_used: str
    detail: str = ""


async def _run_scenario(
    client: AsyncClient, headers: dict, scenario: Scenario, pass_index: int
) -> list[CheckResult]:
    results: list[CheckResult] = []
    history: list[dict] = []
    for turn_index, turn in enumerate(scenario.turns):
        message = turn.pick(pass_index)
        resp = await client.post(
            "/chat", json={"message": message, "history": history}, headers=headers
        )
        results.append(
            CheckResult(
                scenario.name, turn_index, f'POST /chat "{message}" returns 200',
                resp.status_code == 200, message, str(resp.status_code),
            )
        )
        body = resp.json()
        history.append({"role": "user", "text": message})
        history.append({"role": "assistant", "text": body.get("reply", "")})

        if turn.expected_intent is not None:
            actual = body.get("intent")
            results.append(
                CheckResult(
                    scenario.name, turn_index, f'intent == "{turn.expected_intent}"',
                    actual == turn.expected_intent, message, f'got "{actual}"',
                )
            )

        for check in turn.checks:
            passed, desc = check(body["cart"])
            results.append(CheckResult(scenario.name, turn_index, desc, passed, message))

    return results


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--repeat", type=int, default=3,
        help="Number of passes over the whole suite, cycling through each turn's phrasing "
             "variants (default: 3). Keep at or below the smallest variant count per turn "
             "(currently 2-4) to avoid a pass silently repeating an earlier phrasing verbatim.",
    )
    parser.add_argument("--quiet", action="store_true", help="Only print the final aggregated summary.")
    args = parser.parse_args()

    email = f"convo-eval-{int(time.time())}@gmail.com"
    all_results: list[CheckResult] = []

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://eval") as client:
        signup = await client.post(
            "/auth/signup",
            json={"email": email, "password": "Password123!", "name": "Conversation Eval Bot"},
        )
        signup.raise_for_status()
        headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

        for pass_index in range(args.repeat):
            if not args.quiet:
                print("\n" + "#" * 88)
                print(f"# PASS {pass_index + 1}/{args.repeat}")
                print("#" * 88)

            for scenario in SCENARIOS:
                # Independent scenarios: a leftover item from a previous
                # scenario could false-positive a later contains() check.
                await client.post("/chat", json={"message": "clear my cart", "history": []}, headers=headers)

                if not args.quiet:
                    print("\n" + "=" * 88)
                    print(f"SCENARIO: {scenario.name}")
                    print("=" * 88)

                results = await _run_scenario(client, headers, scenario, pass_index)
                all_results.extend(results)
                if not args.quiet:
                    for r in results:
                        mark = "PASS" if r.passed else "FAIL"
                        suffix = f" ({r.detail})" if r.detail and not r.passed else ""
                        print(f'  [{mark}] {r.description} — "{r.message_used}"{suffix}')

    # Aggregate across passes: group by (scenario, turn, check description) so
    # a check that's e.g. 2/3 across phrasing variants is visible as ONE row,
    # not three separate pass/fail lines a reader has to mentally merge.
    grouped: dict[tuple[str, int, str], list[CheckResult]] = {}
    for r in all_results:
        grouped.setdefault((r.scenario, r.turn_index, r.description), []).append(r)

    print("\n" + "=" * 88)
    print(f"AGGREGATED RESULTS ({args.repeat} pass(es))")
    print("=" * 88)
    total_checks = 0
    total_passed = 0
    flaky_or_failing: list[tuple[str, list[CheckResult]]] = []
    for (scenario_name, _turn_index, description), group in grouped.items():
        passed = sum(1 for r in group if r.passed)
        total_checks += len(group)
        total_passed += passed
        if passed < len(group):
            flaky_or_failing.append((f"{scenario_name} :: {description}", group))

    print(f"\nTOTAL: {total_passed}/{total_checks} checks passed across {args.repeat} pass(es)\n")

    if flaky_or_failing:
        print("Checks that did NOT pass every pass (real signal, not noise — investigate):")
        for label, group in flaky_or_failing:
            passed = sum(1 for r in group if r.passed)
            print(f"  [{passed}/{len(group)}] {label}")
            for r in group:
                if not r.passed:
                    print(f'      FAILED on phrasing: "{r.message_used}" ({r.detail})')
    else:
        print(f"Every check passed on every pass, across all phrasing variants used.")


if __name__ == "__main__":
    asyncio.run(main())
