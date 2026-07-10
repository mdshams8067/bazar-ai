# Bazar AI

An AI-assisted grocery shopping experience for the Bangladeshi market — tell it what you're cooking, and it fills your cart with real, in-stock products. Inspired by Shwapno, built independently as a take-home project.

## Data pipeline

1. **Scrape** — a polite, `robots.txt`-compliant scrape of Shwapno.com, a real Bangladeshi grocery retailer (`scrapper/scraper.py`). Product listings are client-side rendered, so this uses Playwright (headless Chromium) rather than a plain HTTP fetch, scraping category pages via infinite scroll in batches instead of one request per product. Honest `User-Agent`, 2-second minimum delay between page loads, no `/api*` paths or query strings touched.
2. **Transform** — `scrapper/transform_to_seed.py` cleans the raw scrape into a ready-to-seed catalog: dedupes by product URL, parses unit/size out of each product name, and assigns stock levels (mostly randomized, with a few products deliberately forced out of stock to exercise the AI assistant's substitution logic later on). Bangla names are left blank — not scraped yet.

Output: `backend/seed/seed_data.json`, the catalog the backend seeds its database from.

## Bazar Buddy, the AI shopping assistant

The differentiator: a function-calling agent, not a Q&A chatbot. Tell it what you're cooking ("morog polao for 6", "biryani under 1500 taka") and it interprets the request, matches ingredients against the real catalog, and fills your cart — substituting or honestly skipping whatever's out of stock.

- **LLM layer** (`backend/core/llm.py`) — Gemini as the primary provider, Groq as an automatic fallback on rate-limit errors, and a local cache so an identical prompt never costs a second API call.
- **Agent** (`backend/agent/`) — one LLM call per message turns free text into structured JSON (intent, dish, ingredients, quantities); everything after that — matching against the catalog, stock checks, substitutions, budget-fitting, the reply text — is deterministic code, not a second model call. The core design principle: the LLM decides *what* the customer wants, plain code decides the *facts* (price, stock, which real product).
- **`POST /chat`** (`backend/routers/chat.py`) connects the two: runs the agent, then merges whatever it matched into the customer's real cart through the same code path the regular "add to cart" endpoint uses. Also handles cart-management requests — remove an item, empty the cart, keep only certain items, or swap one ingredient for another mid-conversation ("make it beef" after ordering chicken biryani) — all against the customer's actual cart, not the catalog.

## Backend

FastAPI, fully async (SQLAlchemy 2.0 `AsyncSession` end to end), Postgres in production / SQLite locally via one `DATABASE_URL` swap, Alembic migrations.

- **Auth** — Supabase Auth, not a hand-rolled system. The frontend signs up/logs in directly against Supabase's own API (`@supabase/supabase-js`); this backend never sees a password and issues no tokens of its own — it only verifies the token Supabase already issued, against their public JWKS (ES256, asymmetric — no shared secret to protect). A `profiles` table holds the one thing Supabase's own schema has no place for (name/phone), keyed to the same id Supabase assigns, and is created lazily on a user's first authenticated request.
- **Products** — paginated listing, category filter, search.
- **Cart** — add/update/remove, always re-validated against live stock.
- **Orders** — checkout snapshots price and product name onto each order line (so order history stays readable even if a product's price or listing changes later), decrements stock, and clears the cart in one transaction.
- **Payments** — SSLCommerz (sandbox) or cash on delivery, picked at checkout. Online payment redirects to SSLCommerz's real hosted checkout page and is only confirmed after a server-to-server validation call (`backend/routers/payment.py`) — never trusted from the browser redirect alone.

## Frontend

React + Vite + Tailwind, installable as a PWA. Product browsing, cart, checkout, order history, and a Bazar Buddy chat widget available from anywhere in the app.

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
