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
- **Matching: two pipeline stages, Layer 1 (retrieval) then Layer 2 (decision)** — not two ranked-by-importance options, two steps that always both run, in that order, on every request. **Layer 1 finds candidates:** exact term-matching first, a fuzzy-match fallback second — both unconditional. Only if *both* of those find nothing, and only if `ENABLE_EMBEDDING_MATCH=true`, does a third method kick in: embedding-similarity search, widening the net for genuine vocabulary mismatches an exact/fuzzy string comparison can't bridge (e.g. "chickpea flour" vs. the catalog's "Gram Flour" — zero shared substring, but the same thing). This embedding step is the *only* optional piece in the whole matcher — off by default, since a working deployed app already exists, so it stays a reversible, config-flag addition, not a rewrite; flip `ENABLE_EMBEDDING_MATCH` off and behavior is byte-for-byte identical to the keyword-only cascade. **Layer 2 decides what to do with whatever Layer 1 found:** stock checks, price sanity, pack-size fit, substitution tiers, the specific-variant honesty check below — always the same deterministic logic, regardless of which of Layer 1's three methods produced the candidate. That's deliberate: Layer 2 has to stay auditable no matter how Layer 1's retrieval methods change over time. Calibrating the embedding-similarity threshold against this session's real matcher bugs (replayed as test pairs against the real catalog) found the margin between a genuine match and a known false positive uncomfortably thin compared to the fuzzy-match fix's — a good illustration of why Layer 2 stays deterministic no matter how Layer 1 evolves. Since a rotated-to fallback embedding model isn't guaranteed to share a comparable vector space with the primary one, every stored embedding (product and query alike) is tagged with the model that produced it, and only same-model vectors are ever compared. Query-time embeddings are cached in the same database as everything else, not a local file, so a redeploy never re-pays for an ingredient phrasing it's already embedded.
- **Substitution cascade** (`backend/agent/stock.py`) — brand swap (same item, different brand in stock) → functional swap (a different single product that serves the same purpose, e.g. ghee → soybean oil) → **DIY substitute recipe**: for an essential ingredient with no single product that can stand in for it at all (heavy cream isn't carried in this catalog under any brand), the LLM proposes a small recipe of other basic ingredients that approximates it (e.g. butter + milk), and code matches every component against the real, in-stock catalog — only used if *all* components are actually available, never a half-added recipe → honest "unavailable" flag if nothing above worked. Same discipline as everywhere else in this agent: the LLM proposes, real stock data decides.
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
cp .env.example .env   # fill in DATABASE_URL, SUPABASE_URL, GOOGLE_API_KEY at minimum
alembic upgrade head
python -m seed.seed_db
uvicorn main:app --reload
```

Optional — only needed if you set `ENABLE_EMBEDDING_MATCH=true` (see Bazar Buddy section above): `python -m seed.embed_products` backfills a Gemini embedding vector for every product, one-off, safe to re-run any time.

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
- **The optional embedding-retrieval addition (`ENABLE_EMBEDDING_MATCH`) isn't backfilled for the full catalog.** Gemini's embedding API free tier caps at 1,000 requests/day *per key*; backfilling all 2,807 products (`seed/embed_products.py`) hit that cap partway through, at ~900, before multi-key rotation existed. The script is safe to re-run (skips already-embedded products by default) and the feature degrades gracefully either way — an un-embedded product is simply invisible to this retrieval tier and falls back to today's exact/fuzzy-only behavior, same as with the flag off entirely. Multiple keys (`GOOGLE_API_KEYS_EXTRA`) stretch this further but a real production deployment at this catalog size would still want a paid tier (or a self-hosted embedding model) rather than relying on free-tier keys.
- **The Flutter mobile app doesn't build for iOS in this submission** — Xcode is required and only runs on macOS; this was built on Linux. The codebase itself is platform-agnostic and needs no changes to build for iOS given a Mac.
