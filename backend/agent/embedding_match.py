"""
agent/embedding_match.py — Layer 1 (retrieval) addition: embedding
retrieval + reranking.

Purely a wider net for finding candidates when agent/matcher.py's exact
term-scoring AND fuzzy_match both find nothing — e.g. "chickpea flour" has
zero shared substring with the catalog's "BPM Gram Flour 500gm" and scores
well under fuzzy_match's threshold, but the two are obviously the same
thing to anyone who knows what besan is. Every downstream decision (stock,
price sanity, substitution tiers, specific-variant honesty check) is
untouched — this module only returns a candidate, never decides anything
about it. See matcher.py's match_product() for where this plugs into the
existing cascade.

Three stages, not two:
1. cosine_topk() — cheap, embedding-only retrieval, widened to a top-K
   shortlist rather than a hard similarity cutoff (see PROJECT_CONTEXT.md:
   a bare cosine-similarity threshold on this catalog's short product
   labels had an uncomfortably thin margin between genuine matches and
   known false positives). Just narrows a category (or, when category_hint
   comes back as something not in the real catalog, the whole 2,807-item
   fallback pool) down to a handful of plausible candidates — and doubles
   as a safety net on its own: verified live that a real "full catalog"
   query (truffle oil, after category_hint fell back to "other") found
   *zero* candidates above this floor, so a known trap (truffle-flavored
   candy) never even reached the reranker.
2. rerank_and_select() — a cross-encoder reranker (core/jina_client.py)
   re-scores that shortlist against the actual query text, which is far
   more decisive than raw cosine similarity: verified live that genuine
   synonyms and known false positives separate by a wide margin once the
   model considers query and candidate together.
3. _llm_verify_and_select() — an LLM call over the reranker's top 3, added
   after live testing proved margin/score alone cannot catch every false
   positive: a reranker always produces *a* top pick even when nothing in
   the pool is genuinely right, and that forced pick can be just as
   confident (both in absolute score AND margin over the runner-up) as a
   genuinely correct one. Verified live: "fried onion" (no such product
   in this catalog) confidently topped "Shwapno Fried Cumin Powder" with
   a 0.23 margin — wider than most real synonym matches — purely because
   both share the literal word "fried"; "foie gras" confidently topped
   "Duck (Hash) Meat Regular" because the parser's own search_terms
   ("duck liver", "goose liver") leaked into the query text. No margin or
   score cutoff separates these from genuine matches, because the
   reranker has no notion of "nothing here is right" — it only ranks
   relative fit within whatever pool it's given. Passing the top 3 (not
   just the top 1) to the LLM also recovers cases where reranking itself
   is slightly off but a correct candidate is sitting at #2 or #3, rather
   than forcing an accept/reject call on the #1 pick alone.

RERANK_MIN_SCORE below is a coarse, cheap pre-filter only — skips the LLM
call entirely on a genuinely degenerate shortlist (everything scoring far
below anything seen in calibration) — not the real accept/reject
decision, which is stage 3.

No vector database, no pgvector: candidate pools here are already small
(category-filtered, in-memory), so plain numpy cosine similarity over a
JSON-stored embedding column is simpler and keeps SQLite-local /
Postgres-prod parity intact (pgvector's `vector` column type is
Postgres-only — see PROJECT_CONTEXT.md for the fuller trade-off writeup).
"""
import logging

import numpy as np

from models.product import Product

logger = logging.getLogger(__name__)

# Loose on purpose — this is a shortlist for the reranker to actually
# judge, not the accept/reject decision itself. Verified live it's also a
# real safety net in its own right: a full-catalog (2,807 product) query
# for "truffle oil" found zero candidates above this floor, correctly
# never reaching the reranker at all — and reranking the full catalog
# directly isn't even possible (verified: Jina's rerank endpoint 422s on
# a document list that large), so this pre-filter is load-bearing, not
# just an optimization.
COSINE_PREFILTER_FLOOR = 0.3
TOP_K_FOR_RERANK = 15

# A coarse, cheap pre-filter only — skips the LLM verification call on a
# genuinely degenerate shortlist (every candidate scoring far below
# anything seen in calibration, -0.06 to +0.13 for genuine matches). Not
# the real accept/reject decision: live testing proved a margin/score
# cutoff alone can't separate genuine matches from confident-but-wrong
# forced picks (see module docstring) — that's _llm_verify_and_select()'s
# job now.
RERANK_MIN_SCORE = -0.12
# How many of the reranker's top candidates the LLM verification step
# considers — >1 so a slightly-off reranking (right answer at #2/#3, not
# #1) can still be recovered instead of forcing an accept/reject call on
# the #1 pick alone.
TOP_K_FOR_VERIFY = 3

_VERIFY_SYSTEM_PROMPT = """You are checking a short list of grocery catalog products against one ingredient a customer asked for. An automated retrieval step has already narrowed the whole catalog down to these candidates and ranked them — but that automated ranking sometimes gets confused by shared words that don't mean the same product (e.g. ranking "fried cumin powder" highest for "fried onion" just because both share the word "fried", or ranking "duck meat" highest for "foie gras" because a related search term mentioned "duck liver").

Look at every candidate and decide: which ONE, if any, would a shopper who asked for the ingredient consider an honest fulfillment of that request — either literally the same thing (a different brand/spelling/size of the same product), or a real functional substitute experienced cooks would recognize and knowingly accept (same role in a recipe)?

Reject a candidate that only shares a word, category, or loose association with the ingredient but is actually a different TYPE of product/ingredient entirely — e.g. "duck meat" is not a substitute for "foie gras" (a specific liver preparation, not just any duck product); "cream cheese" is not "heavy cream" (different product, not interchangeable); a spice powder is not a substitute for a garnish like fried onion, even if both are "fried".

Do NOT reject just because the candidate is a more generic cut, size, pack, or variant of the SAME ingredient — e.g. "duck meat" (unspecified cut) IS an acceptable candidate for "duck breast" (a specific cut of the same animal), and "beef" (unspecified cut) IS acceptable for "wagyu beef" or "beef tenderloin". A separate downstream check already flags and honestly labels cut/variant-specific substitutions like these — your only job here is ruling out genuinely wrong ingredients, not picking the most precise cut.

Accept a candidate that is genuinely the same ingredient under another name/brand/cut, or a substitute a real cook would reach for — e.g. "clarified butter" for "ghee" (the same thing), "gram flour"/"besan" for "chickpea flour" (the same thing), "duck meat" (any cut) for "duck breast" (a specific cut of duck, same animal/ingredient).

Respond with ONLY the candidate's number (e.g. "2"). If none of the candidates are a genuine match or reasonable substitute, respond with exactly: NONE"""


def _llm_verify_and_select(
    ingredient_name: str, candidates: list[Product]
) -> Product | None:
    """Asks the LLM to pick the one genuine match/substitute (if any) among
    up to TOP_K_FOR_VERIFY reranked candidates — see module docstring for
    why a margin/score cutoff on the reranker's output alone isn't enough.
    Fails closed (returns None, same as "no embedding match") on any LLM
    error, consistent with rerank_and_select()'s own fail-closed behavior
    on a rerank() failure — this tier is strictly a wider net, never a
    required step, so an outage here just means falling back to whatever
    exact/fuzzy/DIY-substitute tiers already handle."""
    from core.llm import chat

    # Real product names, not embedding_source_text: the enriched text is
    # tuned for embedding/reranking (deliberately stripped of brand/pack
    # noise so vectors focus on the core ingredient concept — see
    # seed/enrich_labels.py), which can collapse genuinely different
    # products down to identical or near-identical strings. Verified live
    # this is a real, reproducible failure mode, not a hunch: two
    # different real egg products' enriched text both read exactly "egg
    # dim" — sent to the LLM that way, it rejected all candidates (NONE)
    # 10/10 trials; the identical candidates with real product names
    # instead ("KaziFarms Kitchen Branded Egg (12Pcs Pack)" / "Egg
    # Loose") were correctly accepted 10/10 trials, same prompt otherwise
    # unchanged — and re-verified across every other calibration case
    # (chickpea flour, soybean oil, heavy cream, wagyu, etc.) to confirm
    # this wasn't specific to eggs or a regression elsewhere. An LLM
    # asked to tell candidates apart needs the distinguishing text a
    # human would actually read, not the deliberately-flattened version
    # built for a different job (embedding similarity).
    lines = "\n".join(f"{i + 1}. {p.name_en}" for i, p in enumerate(candidates))
    user = f'Ingredient requested: "{ingredient_name}"\nCandidates (most-likely-first, per automated retrieval):\n{lines}'
    try:
        response = chat(
            _VERIFY_SYSTEM_PROMPT, user, max_tokens=8, temperature=0.0,
            should_cache=lambda r: r.strip().upper() != "NONE",
        )
    except Exception:
        logger.exception("[embedding_match] LLM verification call failed; rejecting to be safe")
        return None

    response = response.strip().upper()
    if response.startswith("NONE"):
        logger.info(f"[embedding_match] LLM verification rejected all candidates for {ingredient_name!r}")
        return None

    import re

    m = re.match(r"(\d+)", response)
    if not m:
        logger.warning(f"[embedding_match] unparseable LLM verification response: {response!r}")
        return None

    idx = int(m.group(1)) - 1
    if 0 <= idx < len(candidates):
        return candidates[idx]
    return None


def cosine_topk(
    query_vector: list[float], query_model: str, pool: list[Product], top_k: int = TOP_K_FOR_RERANK
) -> list[tuple[float, Product]]:
    """Cosine similarity between query_vector and every pool product's
    stored embedding — but ONLY products embedded with the same model as
    the query (query_model, from core/embeddings.py's per-call model_used —
    a provider/model switch can mean a query lands on a different model
    than most of the catalog was backfilled with). Comparing vectors
    across two different embedding models isn't guaranteed meaningful even
    at matching dimensions, so a product embedded with a different model
    is treated exactly like one with no embedding at all: invisible here.
    Returns up to top_k (similarity, product) pairs above
    COSINE_PREFILTER_FLOOR, sorted descending — a shortlist for
    rerank_and_select() to actually judge, not a final answer."""
    q = np.asarray(query_vector, dtype=float)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return []

    scored: list[tuple[float, Product]] = []
    for p in pool:
        if not p.embedding or p.embedding_model != query_model:
            continue
        v = np.asarray(p.embedding, dtype=float)
        v_norm = np.linalg.norm(v)
        if v_norm == 0:
            continue
        similarity = float(np.dot(q, v) / (q_norm * v_norm))
        if similarity >= COSINE_PREFILTER_FLOOR:
            scored.append((similarity, p))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:top_k]


def rerank_and_select(query_text: str, shortlist: list[Product], ingredient_name: str) -> Product | None:
    """Reranks shortlist against query_text, then asks an LLM to verify/
    select among the top TOP_K_FOR_VERIFY candidates (see
    _llm_verify_and_select and the module docstring for why a bare
    margin/score cutoff on the reranker's own output isn't reliable
    enough on its own). Returns at most one product — matcher.py unions
    this with fuzzy's candidates the same way either way."""
    if not shortlist:
        return None

    from core.jina_client import rerank

    documents = [p.embedding_source_text or p.name_en for p in shortlist]
    try:
        ranked = rerank(query_text, documents)
    except Exception:
        logger.exception("[embedding_match] rerank call failed; skipping this tier")
        return None
    if not ranked:
        return None

    top_idx, top_score = ranked[0]
    if top_score < RERANK_MIN_SCORE:
        logger.info(f"[embedding_match] rerank top score {top_score:.4f} below floor, rejecting")
        return None

    verify_pool = [shortlist[idx] for idx, _ in ranked[:TOP_K_FOR_VERIFY]]
    return _llm_verify_and_select(ingredient_name, verify_pool)


def embedding_candidates(
    query_vector: list[float], query_model: str, query_text: str, pool: list[Product], ingredient_name: str
) -> list[Product]:
    """Same shape as matcher.fuzzy_match's return (plain product list) so
    matcher.py can union the two candidate lists uniformly.

    rerank_and_select() makes a single confident-or-nothing call — but a
    single winning product isn't enough for match_product()'s downstream
    logic to do its job: picking the best-fitting pack size, or noticing
    an equally-relevant brand is out of stock, both need to compare
    *several* real candidates, not just the one embedding happened to
    rank first. So once a winner is confirmed, every other pool product
    that's a genuine sibling — same core product, different brand/pack
    size — is gathered via an exact match on embedding_source_text and
    returned alongside it. This works because enrichment deliberately
    strips brand/pack noise (seed/enrich_labels.py): verified live that
    all 9 soyabean-oil products across 5 brands collapse to the
    identical enriched string ("soyabean oil soybean oil cooking oil
    tel"), and every real pack size of plain Coca-Cola does too — while
    genuinely different products (Coca-Cola Zero/Diet/Light) get
    distinct text and are correctly excluded. Not bounded by cosine's
    top-15 or the reranker's top-K the way asking the LLM to enumerate
    candidates itself would be — this catches every sibling in the pool,
    however many there are.

    Found live: "soybean oil" with only the 1L Rupchanda pack out of
    stock and a 150ml need used to buy a single 5L bottle (a 33x
    overshoot) because the embedding tier hands the downstream logic
    exactly one candidate to work with; grouping siblings here lets it
    pick a properly-sized pack from the real options instead."""
    shortlist = [p for _, p in cosine_topk(query_vector, query_model, pool)]
    winner = rerank_and_select(query_text, shortlist, ingredient_name)
    if winner is None:
        return []

    winner_text = winner.embedding_source_text
    if not winner_text:
        return [winner]

    siblings = [p for p in pool if p.id != winner.id and p.embedding_source_text == winner_text]
    return [winner] + siblings
