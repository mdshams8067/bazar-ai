"""
agent/embedding_match.py — Layer 1 (retrieval) addition: embedding-similarity
candidate search.

Purely a wider net for finding candidates when agent/matcher.py's exact
term-scoring AND fuzzy_match both find nothing — e.g. "chickpea flour" has
zero shared substring with the catalog's "BPM Gram Flour 500gm" and scores
well under fuzzy_match's threshold, but the two are obviously the same
thing to anyone who knows what besan is. Every downstream decision (stock,
price sanity, substitution tiers, specific-variant honesty check) is
untouched — this module only returns a candidate list, never decides
anything about them. See matcher.py's match_product() for where this plugs
into the existing cascade, and core/embeddings.py for how the vectors
themselves are computed.

No vector database, no pgvector: candidate pools here are already small
(category-filtered, in-memory), so plain numpy cosine similarity over a
JSON-stored embedding column is simpler and keeps SQLite-local /
Postgres-prod parity intact (pgvector's `vector` column type is
Postgres-only — see PROJECT_CONTEXT.md for the fuller trade-off writeup).
"""
import numpy as np

from models.product import Product

# Calibrated against real Gemini embedding calls (gemini-embedding-001) on
# this exact catalog, replaying the session's real bugs as test pairs:
#   chickpea flour/besan -> "BPM Gram Flour 500gm"   = 0.728  (genuine — want a match)
#   caviar/fish roe      -> "Koi Fish Process Cultured" = 0.662  (false positive — want rejected)
#   foie gras            -> "Beef T-Bone Steak"       = 0.593  (false positive — want rejected)
#   foie gras            -> "Chicken Liver"           = 0.745  (arguably plausible, not currently modeled)
# The genuine match and the caviar/Koi-fish false positive this project
# already had to fix once are only 0.066 apart — a much thinner safety
# margin than the deterministic fuzzy-match fix achieved (that pair scores
# ~33 vs. ~78 on token_sort_ratio, a wide gap). 0.70 is the highest
# threshold that still catches the chickpea-flour case while rejecting
# every known false positive above — worth revisiting if the catalog or
# embedding model changes, since this margin has little room to spare.
EMBEDDING_SIM_THRESHOLD = 0.70


def cosine_topk(query_vector: list[float], pool: list[Product]) -> list[tuple[float, Product]]:
    """Cosine similarity between query_vector and every pool product's
    stored embedding. Skips products with no embedding yet (e.g. added
    after the last backfill run — see seed/embed_products.py). Returns
    (similarity, product) pairs above EMBEDDING_SIM_THRESHOLD, sorted
    descending."""
    q = np.asarray(query_vector, dtype=float)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return []

    scored: list[tuple[float, Product]] = []
    for p in pool:
        if not p.embedding:
            continue
        v = np.asarray(p.embedding, dtype=float)
        v_norm = np.linalg.norm(v)
        if v_norm == 0:
            continue
        similarity = float(np.dot(q, v) / (q_norm * v_norm))
        if similarity >= EMBEDDING_SIM_THRESHOLD:
            scored.append((similarity, p))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored


def embedding_candidates(query_vector: list[float], pool: list[Product]) -> list[Product]:
    """Same shape as matcher.fuzzy_match's return (plain product list, best
    first) so matcher.py can union the two candidate lists uniformly."""
    return [p for _, p in cosine_topk(query_vector, pool)]
