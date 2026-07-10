# Bazar AI

An AI-assisted grocery shopping experience for the Bangladeshi market — tell it what you're cooking, and it fills your cart with real, in-stock products.

This repo is being built in stages.

## Data pipeline

1. **Scrape** — a polite, `robots.txt`-compliant scrape of Shwapno.com, a real Bangladeshi grocery retailer (`scrapper/scraper.py`). Product listings are client-side rendered, so this uses Playwright (headless Chromium) rather than a plain HTTP fetch, scraping category pages via infinite scroll in batches instead of one request per product. Honest `User-Agent`, 2-second minimum delay between page loads, no `/api*` paths or query strings touched.
2. **Transform** — `scrapper/transform_to_seed.py` cleans the raw scrape into a ready-to-seed catalog: dedupes by product URL, parses unit/size out of each product name, and assigns stock levels (mostly randomized, with a few products deliberately forced out of stock to exercise the AI assistant's substitution logic later on). Bangla names are left blank — not scraped yet.

Output: `backend/seed/seed_data.json`, the catalog the backend seeds its database from.

## Bazar Buddy, the AI shopping assistant

The differentiator: a function-calling agent, not a Q&A chatbot. Tell it what you're cooking ("morog polao for 6", "biryani under 1500 taka") and it interprets the request, matches ingredients against the real catalog, and fills your cart — substituting or honestly skipping whatever's out of stock.

- **LLM layer** (`backend/core/llm.py`) — Gemini as the primary provider, Groq as an automatic fallback on rate-limit errors, and a local cache so an identical prompt never costs a second API call.
- **Agent** (`backend/agent/`) — one LLM call per message turns free text into structured JSON (intent, dish, ingredients, quantities); everything after that — matching against the catalog, stock checks, substitutions, budget-fitting, the reply text — is deterministic code, not a second model call. The core design principle: the LLM decides *what* the customer wants, plain code decides the *facts* (price, stock, which real product).
- **`POST /chat`** (`backend/routers/chat.py`) connects the two: runs the agent, then merges whatever it matched into the customer's real cart through the same code path the regular "add to cart" endpoint uses. Also handles cart-management requests ("remove the sugar", "empty my cart") against the customer's actual cart, not the catalog.

## Backend

FastAPI, fully async (SQLAlchemy 2.0 `AsyncSession` end to end), Postgres in production / SQLite locally via one `DATABASE_URL` swap, Alembic migrations.

- **Auth** — JWT bearer tokens, bcrypt password hashing (thread-pooled so it never blocks the async event loop). Signup enforces password complexity (upper/lower/digit/symbol) and checks the email domain can actually receive mail (DNS/MX lookup, not just format), both mirrored live in the signup form.
- **Products** — paginated listing, category filter, search.
- **Cart** — add/update/remove, always re-validated against live stock.
- **Orders** — checkout snapshots price and product name onto each order line (so order history stays readable even if a product's price or listing changes later), decrements stock, and clears the cart in one transaction.
- **Payments** — SSLCommerz (sandbox) or cash on delivery, picked at checkout. Online payment redirects to SSLCommerz's real hosted checkout page and is only confirmed after a server-to-server validation call (`backend/routers/payment.py`) — never trusted from the browser redirect alone.

## Frontend

React + Vite + Tailwind, installable as a PWA. Product browsing, cart, checkout, order history, and a Bazar Buddy chat widget available from anywhere in the app.

## Getting started

**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GOOGLE_API_KEY at minimum
alembic upgrade head
python -m seed.seed_db
uvicorn main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```
