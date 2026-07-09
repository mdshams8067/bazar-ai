# Bazar AI

An AI-assisted grocery shopping experience for the Bangladeshi market — tell it what you're cooking, and it fills your cart with real, in-stock products.

This repo is being built in stages; these first commits cover the product catalog.

## Data pipeline

1. **Scrape** — a polite, `robots.txt`-compliant scrape of Shwapno.com, a real Bangladeshi grocery retailer (`scrapper/scraper.py`). Product listings are client-side rendered, so this uses Playwright (headless Chromium) rather than a plain HTTP fetch, scraping category pages via infinite scroll in batches instead of one request per product. Honest `User-Agent`, 2-second minimum delay between page loads, no `/api*` paths or query strings touched.
2. **Transform** — `scrapper/transform_to_seed.py` cleans the raw scrape into a ready-to-seed catalog: dedupes by product URL, parses unit/size out of each product name, and assigns stock levels (mostly randomized, with a few products deliberately forced out of stock to exercise the AI assistant's substitution logic later on). Bangla names are left blank — not scraped yet.

Output: `backend/seed/seed_data.json`, the catalog the backend seeds its database from.
