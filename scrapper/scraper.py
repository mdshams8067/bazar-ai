#!/usr/bin/env python3
"""
Shwapno.com Product Scraper
============================
Polite, robots.txt-compliant scraper using Playwright (headless Chromium).
Scrapes category pages with infinite scroll to collect grocery product data.

robots.txt rules respected:
  - Never call /api*
  - Never use query strings (except ?lang=en which is allowed)
  - Only fetch clean paths: sitemap, category pages, product pages
  - User-Agent is honest and identifiable
  - Rate limit: minimum 2 seconds between requests
"""

import asyncio
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright, Page, ElementHandle

# =============================================================================
# CONFIGURATION — All selectors, URLs, and settings in one place
# =============================================================================

# User agent
USER_AGENT = "ShwapnoDemoScraper/1.0 (personal portfolio project)"

# Rate limiting
MIN_DELAY_SECONDS = 2.0          # Minimum delay between page loads
SCROLL_DELAY_SECONDS = 2.5       # Delay after each scroll for content to load
PAGE_LOAD_TIMEOUT_MS = 45_000    # Timeout for page navigation
MAX_SCROLLS_PER_PAGE = 30        # Safety cap on scrolls per category page

# Sitemap
SITEMAP_INDEX_URL = "https://www.shwapno.com/sitemap.xml"
SITEMAP_CATEGORIES_URL = "https://www.shwapno.com/sitemap-categories.xml"
BASE_URL = "https://www.shwapno.com"

# Priority categories — these are the ones we want for a recipe-to-cart AI
# Maps display_name -> URL slug(s) from the sitemap
PRIORITY_CATEGORIES = [
    # Rice
    "rice", "loose-rice", "packed-rice",
    # Oil
    "oil", "soybean-oil", "mustard-oil", "olive-oil", "rice-bran-oil",
    "sunflower-oil", "flavored-oil",
    # Spices & Seasoning
    "spices", "salt-and-sugar",
    # Meat & Fish
    "meat", "fish", "meat-and-fish",
    # Dal/Lentils
    "daal-or-lentil",
    # Vegetables & Fruits
    "fresh-vegetables", "fresh-fruits", "dry-vegetables", "dry-fruits",
    "fruits-and-vegetables",
    # Dairy & Eggs
    "dairy", "eggs", "liquid-and-uht-milk", "powder-milk", "butter",
    "ghee", "Cheese", "Yogurt", "Laban", "Lacchi",
    "condensed-milk-and-cream",
    # Cooking essentials
    "cooking", "ready-mix", "sauces-and-pickles", "sauces",
    "pickle-and-condiments", "honey", "mayonnaise",
    # Frozen
    "Frozen", "Paratha", "Singara", "Nuggets", "Sausage", "French-Fries",
    "Samosa", "Frozen-Snacks-Others",
    # Baking
    "baking-needs",
    # Breakfast & beverages
    "breakfast", "beverages", "drinking-water",
    # Snacks
    "snacks", "biscuits", "chips-and-pretzels", "Noodles", "Pasta",
    "Macaroni", "cakes", "local-snacks", "popcorn-and-nuts",
    "candy-chocolate", "soup",
    # Canned food
    "canned-food",
    # Bread / cereals
    "cereals", "breads",
    # Jam, jelly, dips
    "jam-and-jelly", "dips-and-spreads",
    # Sweets
    "sweet",
    # Ice cream
    "ice-cream",
]

# Categories to SKIP entirely (per user requirement)
SKIP_CATEGORIES = {
    "beauty-and-health", "home-cleaning", "fashion-and-lifestyle",
    "toys-and-sports", "office-products", "pet-care", "Gadget",
    "home-and-kitchen", "baby-food-and-care", "Diaper", "Combo-Delights",
    # Clothing & accessories
    "women", "men", "topwear-2", "Bottomwear-2", "lungi", "bottomwear",
    "briefs-and-boxers", "vests", "wallets", "belts", "watches",
    "card-holders", "cigarrete-box", "boys-clothing", "girls-clothing",
    "fatua", "trousers", "clothing-sets-2", "dresses", "tops",
    "clothing-sets", "umbrella", "luggages-and-trolleys", "loafers",
    "mens-shoes", "socks", "kurtis-tunics-and-tops", "skirts-and-palazzos",
    # Electronics
    "Fan", "Iron",
    # Stationery
    "writing-and-drawing", "drawing-books", "colours", "pencils",
    "glue-and-tapes", "files-and-folders", "hardware",
    "envelopes-and-stickers", "cutting", "Pencil-Box", "paper",
    "toner-and-ink", "batteries", "Educational-Science-Kits",
    # Toys
    "toys-items", "gaming", "cycling",
    # Baby
    "baby-diapers",
}

# CSS Selectors for product extraction — isolated here for easy adjustment
SELECTORS = {
    "product_box":       ".product-box",
    "product_title":     ".product-box-title a",
    "active_price":      ".active-price",
    "old_price":         ".old-price",
    "product_image":     "img",
    "product_quantity":  ".product-box-quantity",
    "product_attribute": ".product-box-attribute",
    "delivery_info":     ".product-box-delivery-info",
}

# Output paths
OUTPUT_DIR = Path("data")
SCRAPED_FILE = OUTPUT_DIR / "products_scraped.json"

# Logging
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"

# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class Product:
    """Represents a scraped product."""
    name: str
    price_bdt: Optional[float]
    old_price_bdt: Optional[float]
    category: str
    unit: Optional[str]
    url: str
    image_url: Optional[str]
    scraped_at: str = ""

    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()


@dataclass
class ScrapeStats:
    """Tracks scraping progress."""
    total_requests: int = 0
    total_products: int = 0
    total_categories: int = 0
    failed_pages: int = 0
    failed_products: int = 0
    seen_urls: set = field(default_factory=set)
    start_time: float = 0.0

    def __post_init__(self):
        self.start_time = time.time()

    def elapsed(self) -> str:
        elapsed = time.time() - self.start_time
        mins, secs = divmod(int(elapsed), 60)
        return f"{mins}m {secs}s"


# =============================================================================
# PRICE PARSING
# =============================================================================


def parse_price(text: str) -> Optional[float]:
    """Parse a BDT price from text like '৳320', '৳57', 'Tk 320', etc."""
    if not text:
        return None
    # Remove currency symbols, whitespace, commas
    cleaned = text.replace("৳", "").replace("Tk", "").replace(",", "").strip()
    # Extract the first number (integer or decimal)
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


# =============================================================================
# SITEMAP PARSING
# =============================================================================


def fetch_sitemap_urls(url: str) -> list[str]:
    """Fetch and parse a sitemap XML, returning all <loc> URLs."""
    logging.info(f"Fetching sitemap: {url}")
    try:
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15) as client:
            resp = client.get(url)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Could be <urlset> (list of URLs) or <sitemapindex> (list of sitemaps)
        urls = []
        for loc in root.findall(".//s:loc", ns):
            if loc.text:
                urls.append(loc.text.strip())

        logging.info(f"  Found {len(urls)} URLs in sitemap")
        return urls

    except Exception as e:
        logging.error(f"  Failed to fetch sitemap {url}: {e}")
        return []


def get_category_urls() -> list[tuple[str, str]]:
    """
    Get priority category URLs from the sitemap.
    Returns list of (category_name, full_url) tuples.
    """
    all_category_urls = fetch_sitemap_urls(SITEMAP_CATEGORIES_URL)
    time.sleep(MIN_DELAY_SECONDS)

    priority = []
    seen_slugs = set()

    for url in all_category_urls:
        parsed = urlparse(url)
        slug = parsed.path.strip("/")

        # Skip if not in priority list or in skip list
        if slug in SKIP_CATEGORIES:
            continue

        if slug.lower() in {s.lower() for s in PRIORITY_CATEGORIES}:
            if slug.lower() not in seen_slugs:
                seen_slugs.add(slug.lower())
                category_name = slug.replace("-", " ").title()
                priority.append((category_name, url))

    logging.info(f"Selected {len(priority)} priority categories to scrape")
    for name, url in priority:
        logging.info(f"  • {name}: {url}")

    return priority


# =============================================================================
# PRODUCT EXTRACTION
# =============================================================================


async def extract_product(
    box: ElementHandle, category: str, base_url: str
) -> Optional[Product]:
    """
    Extract product data from a single .product-box element.
    Returns None if extraction fails.
    """
    try:
        # Product name and URL
        title_el = await box.query_selector(SELECTORS["product_title"])
        if not title_el:
            return None

        name = (await title_el.inner_text()).strip()
        href = await title_el.get_attribute("href")

        if not name or not href:
            return None

        product_url = href if href.startswith("http") else f"{base_url}{href}"

        # Price
        price_el = await box.query_selector(SELECTORS["active_price"])
        price_text = (await price_el.inner_text()).strip() if price_el else ""
        price = parse_price(price_text)

        # Old/original price (if discounted)
        old_price_el = await box.query_selector(SELECTORS["old_price"])
        old_price_text = (
            (await old_price_el.inner_text()).strip() if old_price_el else ""
        )
        old_price = parse_price(old_price_text)

        # Image URL
        img_el = await box.query_selector(SELECTORS["product_image"])
        image_url = None
        if img_el:
            image_url = await img_el.get_attribute("src")
            if not image_url:
                image_url = await img_el.get_attribute("data-src")

        # Unit / quantity
        qty_el = await box.query_selector(SELECTORS["product_quantity"])
        unit = None
        if qty_el:
            unit_text = (await qty_el.inner_text()).strip()
            if unit_text:
                unit = unit_text

        # If no unit from quantity, try attribute
        if not unit:
            attr_el = await box.query_selector(SELECTORS["product_attribute"])
            if attr_el:
                attr_text = (await attr_el.inner_text()).strip()
                if attr_text:
                    unit = attr_text

        return Product(
            name=name,
            price_bdt=price,
            old_price_bdt=old_price,
            category=category,
            unit=unit,
            url=product_url,
            image_url=image_url,
        )

    except Exception as e:
        logging.debug(f"    Failed to extract product: {e}")
        return None


# =============================================================================
# PAGE SCRAPING WITH INFINITE SCROLL
# =============================================================================


async def scrape_category_page(
    page: Page, category_name: str, url: str, stats: ScrapeStats
) -> list[Product]:
    """
    Navigate to a category page, scroll to load all products,
    and extract product data.
    """
    products = []

    try:
        logging.info(f"Loading: {url}")
        await page.goto(url, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT_MS)
        stats.total_requests += 1

        # Wait for product boxes to appear
        try:
            await page.wait_for_selector(
                SELECTORS["product_box"], timeout=15_000
            )
        except Exception:
            logging.warning(f"  No product boxes found on {url} — may be empty")
            return products

        # Initial product count
        boxes = await page.query_selector_all(SELECTORS["product_box"])
        prev_count = len(boxes)
        logging.info(f"  Initial load: {prev_count} products")

        # Scroll to load all products (infinite scroll)
        scroll_attempts = 0
        stale_scrolls = 0

        while scroll_attempts < MAX_SCROLLS_PER_PAGE:
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(SCROLL_DELAY_SECONDS)
            scroll_attempts += 1

            # Check new product count
            boxes = await page.query_selector_all(SELECTORS["product_box"])
            new_count = len(boxes)

            if new_count > prev_count:
                logging.info(
                    f"  Scroll {scroll_attempts}: {prev_count} → {new_count} products"
                )
                prev_count = new_count
                stale_scrolls = 0
            else:
                stale_scrolls += 1
                # If 2 consecutive scrolls yield nothing, all products are loaded
                if stale_scrolls >= 2:
                    logging.info(
                        f"  All products loaded after {scroll_attempts} scrolls"
                    )
                    break

        # Extract products from all boxes
        boxes = await page.query_selector_all(SELECTORS["product_box"])
        logging.info(f"  Extracting from {len(boxes)} product boxes...")

        for box in boxes:
            product = await extract_product(box, category_name, BASE_URL)
            if product:
                # Deduplicate by URL
                if product.url not in stats.seen_urls:
                    stats.seen_urls.add(product.url)
                    products.append(product)
            else:
                stats.failed_products += 1

        logging.info(
            f"  ✓ Extracted {len(products)} unique products from {category_name}"
        )

    except Exception as e:
        logging.error(f"  ✗ Failed to scrape {url}: {e}")
        stats.failed_pages += 1

    return products


# =============================================================================
# INCREMENTAL SAVE
# =============================================================================


def save_products(all_products: list[Product], filepath: Path):
    """Save products to JSON file (incremental save)."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(p) for p in all_products]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =============================================================================
# MAIN SCRAPER
# =============================================================================


async def run_scraper():
    """Main scraper entry point."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT
    )
    logger = logging.getLogger()

    # Also log to file
    file_handler = logging.FileHandler(
        OUTPUT_DIR / "scraper.log", mode="w", encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    logger.addHandler(file_handler)

    logging.info("=" * 60)
    logging.info("Shwapno.com Product Scraper — Starting")
    logging.info("=" * 60)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Get category URLs from sitemap
    logging.info("\n--- Step 1: Fetching category URLs from sitemap ---")
    categories = get_category_urls()

    if not categories:
        logging.error("No categories found! Exiting.")
        return

    # Step 2: Scrape each category
    logging.info("\n--- Step 2: Scraping category pages ---")

    stats = ScrapeStats()
    all_products: list[Product] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        for i, (cat_name, cat_url) in enumerate(categories, 1):
            logging.info(
                f"\n[{i}/{len(categories)}] Category: {cat_name}"
            )

            # Rate limiting
            if i > 1:
                logging.info(f"  Rate limit: waiting {MIN_DELAY_SECONDS}s...")
                await asyncio.sleep(MIN_DELAY_SECONDS)

            # Scrape
            products = await scrape_category_page(page, cat_name, cat_url, stats)
            all_products.extend(products)
            stats.total_products = len(all_products)
            stats.total_categories += 1

            # Incremental save
            save_products(all_products, SCRAPED_FILE)
            logging.info(
                f"  Saved incrementally — Total: {stats.total_products} products"
            )

            # Progress summary
            logging.info(
                f"  Progress: {stats.total_categories} categories, "
                f"{stats.total_products} products, "
                f"{stats.total_requests} requests, "
                f"{stats.failed_pages} failed pages, "
                f"{stats.failed_products} failed extractions, "
                f"elapsed: {stats.elapsed()}"
            )

        await browser.close()

    # Final summary
    logging.info("\n" + "=" * 60)
    logging.info("SCRAPING COMPLETE")
    logging.info("=" * 60)
    logging.info(f"  Categories scraped:    {stats.total_categories}")
    logging.info(f"  Total products:        {stats.total_products}")
    logging.info(f"  Total page requests:   {stats.total_requests}")
    logging.info(f"  Failed pages:          {stats.failed_pages}")
    logging.info(f"  Failed extractions:    {stats.failed_products}")
    logging.info(f"  Elapsed time:          {stats.elapsed()}")
    logging.info(f"  Output:                {SCRAPED_FILE}")
    logging.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_scraper())
