# Bazar AI

An AI-assisted grocery shopping experience for the Bangladeshi market — tell it what you're cooking, and it fills your cart with real, in-stock products. Inspired by Shwapno, built independently as a take-home project.

**Live demo:** [bazar-ai.vercel.app](https://bazar-ai.vercel.app) — note: the backend runs on Render's free tier, so the first request after a period of inactivity can take up to ~50s to wake up (the app shows a banner while this happens).

## Data pipeline

1. **Scrape** — a polite, `robots.txt`-compliant scrape of Shwapno.com, a real Bangladeshi grocery retailer (`scrapper/scraper.py`). Product listings are client-side rendered, so this uses Playwright (headless Chromium) rather than a plain HTTP fetch, scraping category pages via infinite scroll in batches instead of one request per product. Honest `User-Agent`, 2-second minimum delay between page loads, no `/api*` paths or query strings touched.
2. **Transform** — `scrapper/transform_to_seed.py` cleans the raw scrape into a ready-to-seed catalog: dedupes by product URL, parses unit/size out of each product name, and assigns stock levels (mostly randomized, with a few products deliberately forced out of stock to exercise the AI assistant's substitution logic later on). Bangla names are left blank — not scraped yet.

Output: `backend/seed/seed_data.json`, the catalog the backend seeds its database from.

## Bazar Buddy, the AI shopping assistant

The differentiator: a function-calling agent, not a Q&A chatbot. Tell it what you're cooking ("morog polao for 6", "biryani under 1500 taka") and it interprets the request, matches ingredients against the real catalog, and fills your cart — substituting or honestly skipping whatever's out of stock.

- **LLM layer** (`backend/core/llm.py`) — Gemini as the primary provider, Groq as an automatic fallback on rate-limit errors, and a local cache so an identical prompt never costs a second API call. Both providers rotate across multiple API keys and multiple models before giving up (`core/gemini_client.py`, shared by the embedding matcher below too) — free-tier quota, and occasionally a model itself, runs out at inconvenient times, verified live during development rather than just designed defensively.
- **Agent** (`backend/agent/`) — one LLM call per message turns free text into structured JSON (intent, dish, ingredients, quantities); everything after that — matching against the catalog, stock checks, substitutions, budget-fitting, the reply text — is deterministic code, not a second model call. The core design principle: the LLM decides *what* the customer wants, plain code decides the *facts* (price, stock, which real product).
- **Matching is two layers: Layer 1 finds candidates, Layer 2 decides what to do with them.** Both run on every request, in that order. Layer 2 — stock checks, price sanity, pack-size fit, substitution tiers, the specific-variant honesty check below — is always the same deterministic code, no matter which Layer 1 method produced the candidate. That separation is deliberate: however Layer 1's retrieval evolves, Layer 2 stays auditable.

  **Layer 1 — retrieval, two methods, embedding primary / keyword matching secondary:**
  - **Embedding retrieval (tried first)** is a three-stage pipeline, not a single similarity score: (1) a cheap cosine-similarity pass narrows the whole catalog to a loose top-15 shortlist, comparing against LLM-enriched catalog text rather than raw scraped product names (`seed/enrich_labels.py` generates cleaned, synonym-expanded text per product, once, offline); (2) a cross-encoder reranker (Jina AI's `jina-reranker-v3`) re-scores that shortlist by reasoning over the query and each candidate's text *together*, far more decisive than raw cosine similarity alone; (3) an LLM verification call checks the reranker's top few picks before anything is accepted — added because a reranker's own confidence score turned out not to be a safe signal on its own: it can be just as confident when its forced top pick is wrong as when it's genuinely right (e.g. it once confidently ranked "Fried Cumin Powder" above every real match for a "fried onion" request — a product this catalog doesn't even carry — purely because both share the word "fried"). Embeddings and reranking run on Jina AI (`jina-embeddings-v3` + `jina-reranker-v3`, CC-BY-NC 4.0-licensed — fine for this take-home, not for commercial reuse), with Gemini as an automatic fallback provider if Jina is unavailable. Every stored embedding is tagged with the model that produced it, so a provider switch never silently compares incomparable vectors.
  - **Exact/fuzzy keyword matching (fallback)** — plain substring scoring, then a looser fuzzy match. Runs automatically whenever embedding is off, unavailable (a provider outage), or genuinely finds nothing, so a Jina outage degrades to keyword-only matching rather than breaking the chat feature.
  - **Why embedding is primary, not keyword matching** — this is reversed from the original design, where embedding was an off-by-default last resort only ever consulted when keyword matching found nothing. Live testing found real keyword-matching bugs embedding doesn't share: a generic shared word could win outright (e.g. "flour" matching an unrelated "Tempura Flour" product, permanently blocking the real match — "Maida" — from ever being considered, since the old cascade only tried embedding when keyword matching found *nothing at all*), and an existing tie-break rule could prefer the wrong product on a genuine score tie (e.g. "Sweet Potato" beating plain "Potato" purely for having a shorter name). Embedding got both cases right. `ENABLE_EMBEDDING_MATCH=false` still reverts every ingredient to the original, fully deterministic keyword-only cascade, byte-for-byte — the one-env-var rollback this project has kept available throughout.
  - **The trade-offs, stated plainly, not glossed over:** every ingredient now costs roughly 1-4 seconds of real network latency (the cosine pass, the reranker call, and the verification call are all real requests) instead of keyword matching's sub-millisecond cost — a genuine, user-visible slowdown accepted because keyword matching's own false-positive risk was judged the bigger correctness problem. Brand-substitution's honest "your usual brand is out of stock, here's an equivalent" note also currently doesn't fire when an ingredient resolves via the embedding tier — it returns a single confident product, not the full set of equivalent in-stock brands that note depends on identifying — a known, accepted gap for this submission, not an oversight.
  - **`category_hint`** (which of the catalog's 24 real categories an ingredient belongs to) is generated by the same LLM parsing call as everything else — a guess from general grocery-taxonomy knowledge, not a database lookup — so it isn't trusted blindly. The prompt lists all 24 real categories (13 were missing from an earlier, incomplete version) with explicit examples for this catalog's own non-obvious quirks (pasta is filed under "Snacks," not "Baking Needs"; mayonnaise is "Breakfast," not "Sauces And Pickles"). If the guessed category turns up nothing, matching retries once against the entire catalog before giving up, rather than treating a wrong guess as final.
- **Substitution cascade** (`backend/agent/stock.py`), reached when every candidate Layer 1 found is out of stock — brand swap (same item, different brand in stock, found via its own fresh keyword search of the category) → functional swap (a different single product serving the same purpose, e.g. ghee → soybean oil, via the LLM's `substitute_hint`) → **DIY substitute recipe**: for an essential ingredient with no single product that can stand in for it at all (heavy cream isn't carried in this catalog under any brand), the LLM proposes a small recipe of other basic ingredients that approximates it (e.g. butter + milk), and code matches every component against the real, in-stock catalog — only used if *all* components are actually available, never a half-added recipe → honest "unavailable" flag if nothing above worked. Same discipline as everywhere else in this agent: the LLM proposes, real stock data decides. Two things worth being precise about: (1) this cascade's own brand/functional searches use plain keyword matching internally, not the embedding retrieval described above — so for an ingredient that *only* embedding can find at all (a genuine vocabulary-gap case), if its single embedding-found candidate turns out to be out of stock, this fallback search may not find an alternative even if an in-stock one exists, since it can't see what embedding sees. (2) There's a second, simpler brand-substitution check that runs *before* this cascade is ever reached — inside `match_product()` itself, when the top-scoring candidates are a genuine mix of in-stock and out-of-stock — and *that* one depends on Layer 1 returning the full set of tied candidates; the embedding tier returns one confident product, not a set, so this quicker check doesn't have anything to compare and the substitution goes through as a plain "ok" with no note. Both are the same underlying trade-off from promoting embedding to primary (see above), stated here precisely rather than glossed over.
- **Specific-variant honesty check** (`agent/matcher.py`) — the matcher works by keyword overlap, so "wagyu beef" and "beef" score identically against an ordinary beef product; nothing in a plain term match knows wagyu is a specific, realistically-uncarried premium tier, not just another word for beef. When the LLM flags an ingredient as that kind of named premium/rare variant, a clean match gets double-checked: if the matched product's name doesn't actually contain the specific descriptor, it's rewritten as an honest substitution ("couldn't find wagyu beef specifically — added Beef T-Bone Steak (beef) instead") instead of silently reporting success for something the customer didn't actually get.
- **Two kinds of questions, handled differently on purpose** — "koto dam dim er?" (what's the price of eggs?) needs a real, current fact the LLM doesn't have, so it's a `product_question`: the LLM just flags what's being asked about, and deterministic code states the actual price/stock. "Is olive oil essential to pesto?" or "what can I use instead of heavy cream?" is a different kind of question — one the LLM can genuinely answer from cooking knowledge alone, no live data needed — so it's its own `ingredient_question` intent: a direct conversational answer, plus a relevant follow-up when there's a natural next step (e.g. "want me to add soybean oil instead?"). Keeping these separate matters: forcing both into one intent meant a real, correct answer the LLM had already written was being silently discarded in favor of a generic "couldn't find that product" — the trap of only having one kind of question in mind, discovered by asking it a question the original design hadn't anticipated.
- **`POST /chat`** (`backend/routers/chat.py`) connects the two: runs the agent, then merges whatever it matched into the customer's real cart through the same code path the regular "add to cart" endpoint uses. Also handles cart-management requests — remove an item, empty the cart, keep only certain items, or swap one ingredient for another mid-conversation ("make it beef" after ordering chicken biryani) — all against the customer's actual cart, not the catalog.

## Backend

FastAPI, fully async (SQLAlchemy 2.0 `AsyncSession` end to end), Postgres in production / SQLite locally via one `DATABASE_URL` swap, Alembic migrations.

- **Auth** — Supabase Auth, not a hand-rolled system. An earlier version of this project did roll its own (email format/deliverability checks, password complexity rules, bcrypt hashing, JWT issuance) — it worked, but auth is a commodity, security-critical surface (rate-limiting, lockout, token edge cases) that's easy to get subtly wrong on a short deadline, and a mature managed provider already solves it. The frontend now signs up/logs in directly against Supabase's own API (`@supabase/supabase-js`); this backend never sees a password and issues no tokens of its own — it only verifies the token Supabase already issued, against their public JWKS (ES256, asymmetric — no shared secret to protect). A `profiles` table holds the one thing Supabase's own schema has no place for (name/phone), keyed to the same id Supabase assigns, and is created lazily on a user's first authenticated request.
- **Products** — paginated listing, category filter, search.
- **Cart** — add/update/remove, always re-validated against live stock.
- **Orders** — checkout snapshots price and product name onto each order line (so order history stays readable even if a product's price or listing changes later), decrements stock, and clears the cart in one transaction.
- **Payments** — SSLCommerz (sandbox) or cash on delivery, picked at checkout. Online payment redirects to SSLCommerz's real hosted checkout page and is only confirmed after a server-to-server validation call (`backend/routers/payment.py`) — never trusted from the browser redirect alone.

## Frontend

React + Vite + Tailwind, installable as a PWA. Product browsing, cart, checkout, order history, and a Bazar Buddy chat widget available from anywhere in the app.

## Mobile app (Flutter)

A native Android client (`mobile/`) with full feature parity with the web app — auth, catalog browsing, cart, Bazar Buddy chat (match cards, pack-size picker, quick-reply scaling), checkout (cash on delivery and SSLCommerz), and order history/tracking. It's a second client of the exact same backend and Supabase project as the web app — no separate database, no duplicated auth system, same REST API. The same Cooper Hewitt/Changa One fonts and color palette are ported into Flutter's `ThemeData` rather than falling back to Material defaults, and the app ships with a real launcher icon and display name ("Bazar AI," not the Flutter template default of "mobile") — a simple monogram in the same brand green and Cooper Hewitt Extra Bold used everywhere else, generated once and wired into both Android's launcher (via `flutter_launcher_icons`, proper adaptive icon + legacy sizes) and the web app's favicon/PWA icons, so both clients share one identity instead of a generic placeholder.

The one genuinely tricky part: SSLCommerz's hosted checkout page redirects to a *web* URL on completion (`{FRONTEND_URL}/order-confirmation/{id}?payment=...`), since there's no mobile deep link wired up server-side. The mobile app shows that page in an in-app WebView and detects completion by matching the WebView's navigation requests against that URL pattern (path + query only, so it's host-agnostic), then routes to its own native confirmation screen instead of letting the web page load — verified working end-to-end against the real SSLCommerz sandbox on a real emulator run.

**Build and run:**
```bash
cd mobile
flutter pub get
cp assets/.env.example assets/.env   # fill in SUPABASE_URL, SUPABASE_ANON_KEY (same values as frontend/.env.local)
flutter run                          # or: flutter build apk --release
```

**iOS is not built in this submission** — Xcode (required for any iOS build, including just running on the iOS simulator) only runs on macOS, and this was developed on Linux. This is a hard toolchain constraint, not a scope cut: the Dart/Flutter codebase itself is entirely platform-agnostic and would build for iOS unmodified given access to a Mac.

## Deployment

Frontend on Vercel, backend on Render, database + auth on Supabase — each is running that stack's free tier. This isn't production yet, just a take-home submission, so free tier is the right call for now; an actual production launch would need to upgrade off it (Render's free tier in particular — see the cold-start limitation below).

The split itself isn't arbitrary — it matches what each piece is actually for: Vercel builds and serves the static Vite/React bundle off a CDN with zero server to manage; Render runs the FastAPI app as a real long-lived process (needed for it at all — Vercel's model is serverless functions, not a persistent async app); Supabase was already the choice for the database, so it covering auth too meant no third provider to wire in.

## Getting started

Create a free Supabase project first (supabase.com) — it provides both the Postgres database and auth. From its dashboard, grab: the database connection string (use the **session pooler** URI, not the direct/IPv6-only one), the project URL, and the anon/public API key.

**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL, SUPABASE_URL, GOOGLE_API_KEY, JINA_API_KEY
alembic upgrade head
python -m seed.seed_db
python -m seed.enrich_labels    # one-off: generates cleaned, synonym-expanded text per product
python -m seed.embed_products   # one-off: embeds that text with Jina for every product
uvicorn main:app --reload
```

The last two steps back the primary matching path (embedding retrieval, on by default — see "Bazar Buddy" above) and only need to run once per catalog; both are safe to re-run any time and only fill in what's missing. Without `JINA_API_KEY`, embedding calls automatically fail over to Gemini, and if that fails too, matching falls back to exact/fuzzy keyword search — the app still works either way, just without embedding's vocabulary-gap coverage. Set `ENABLE_EMBEDDING_MATCH=false` to skip all of this and run purely on the deterministic keyword-only cascade.

**Frontend**
```bash
cd frontend
npm install
cp .env.example .env.local   # fill in VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
npm run dev
```

## Testing

- Backend: `pytest` (unit/integration, mocked LLM calls — fast, runs on every change).
- `python -m agent.test_agent` — single-turn acceptance test against the real LLM.
- `python -m agent.test_conversations [--repeat N]` — multi-turn conversational eval suite against the real LLM, the real router, and a real cart: add→remove, add→clear, cook a dish→keep only one ingredient, cook a dish→swap an ingredient (two phrasings), and an off-topic fallback check. `--repeat` cycles through several phrasings of the same request per pass, since a single phrasing working once is weaker evidence than the same intent surviving several people's wording of it.

## Known limitations

- **Signup email confirmation runs on Supabase's default shared email sender, not a custom SMTP provider.** That sender is capped at just 2 emails/hour by default — fine for this project's expected signup volume, but a real production launch should configure a custom SMTP provider (Resend, Postmark, etc.) in Supabase's Auth settings instead, both to lift that limit and to get proper bounce/complaint tracking under your own sending reputation rather than Supabase's shared one.
- **Backend cold starts on Render's free tier** after ~15 minutes of inactivity — the first request afterward can take up to ~50 seconds. The frontend polls `/health` and shows a "waking up" banner rather than hiding the delay. A scheduled GitHub Actions workflow (`.github/workflows/keep-alive.yml`) pings `/health` every 10 minutes to keep the instance warm in practice — though GitHub disables a scheduled workflow automatically after 60 days with no other repo activity, so this isn't a permanent guarantee, just a mitigation.
- **Embedding retrieval being the primary matching path means every ingredient pays real network latency (~1-4 seconds) instead of keyword matching's sub-millisecond cost** — a deliberate, accepted trade-off (see "Bazar Buddy" above for why), not an oversight. `ENABLE_EMBEDDING_MATCH=false` reverts to the original, instant, fully deterministic keyword-only cascade at any time.
- **Jina AI's embedding and reranking models are CC-BY-NC 4.0-licensed — non-commercial use only.** Acceptable for this take-home submission; a commercial deployment would need a different provider or a paid Jina license.
- **`category_hint` is an LLM guess, not a database lookup, so it can still be wrong for a catalog quirk not yet found and hard-coded into the prompt** — the retry-against-full-catalog fallback (see "Bazar Buddy" above) catches most of these, but isn't a guarantee for every possible mismatch.
- **The substitution cascade (brand/functional swap) searches by plain keyword matching internally, not embedding** — so for an ingredient that only embedding can find at all, if that single found candidate is out of stock, the cascade may not find an in-stock alternative even if one exists, since its own search can't see what embedding sees. Narrow in practice (needs both "only embedding finds it" and "that one candidate is out of stock" to be true at once), but a real gap, not a hypothetical one.
- **The Flutter mobile app doesn't build for iOS in this submission** — Xcode is required and only runs on macOS; this was built on Linux. The codebase itself is platform-agnostic and needs no changes to build for iOS given a Mac.
