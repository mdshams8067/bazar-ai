# Bazar AI

An AI-assisted grocery shopping experience for the Bangladeshi market — tell it what you're cooking, and it fills your cart with real, in-stock products.

This repo is being built in stages; this first commit covers data collection.

## Data collection

The product catalog comes from a polite, `robots.txt`-compliant scrape of Shwapno.com, a real Bangladeshi grocery retailer:

- **Tooling:** Playwright (headless Chromium) for the category pages, since product listings are client-side rendered (the server-side HTML is just shimmer placeholders) — plus `httpx` for fetching the sitemap.
- **Strategy:** category pages with infinite scroll, scraped in batches rather than one request per product — far fewer HTTP calls than visiting every product page individually.
- **Politeness:** an honest, identifiable `User-Agent`; a minimum 2-second delay between page loads; no `/api*` paths or query strings touched, per the site's `robots.txt`.
- **Output:** `scrapper/data/products_scraped.json` — raw product data (title, price, unit, image, product URL) per category.

See `scrapper/scraper.py` for the implementation.
