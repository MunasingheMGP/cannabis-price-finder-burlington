"""
Step 3 — Scrape product listings from bestbangforyourbud.com
for stores in Burlington / surrounding cities.
Writes results to PostgreSQL.
"""

import re
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from db_config import get_engine, write_df

#  CONFIG 
BBFYB_CITIES = [
    "Burlington", "Hamilton", "Oakville",
    "Mississauga", "Milton", "Brampton", "Stoney-Creek",
]

BASE_URL = "https://bestbangforyourbud.com"
CITY_URL = BASE_URL + "/en/stores/ON/{city}"
TIMEOUT  = 30
DELAY    = 1.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

PRICE_RE = re.compile(r"\$\s*\d+(?:\.\d{2})?")
PROMO_RE = re.compile(
    r"(sale|promo|deal|special|offer|limited|ends?|until|expires?|off\b)",
    re.IGNORECASE,
)


#  HELPERS 
def get_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


#  LIST STORE URLS FOR A CITY 
def get_store_urls(city: str) -> list[dict]:
    url  = CITY_URL.format(city=city)
    html = get_html(url)
    soup = BeautifulSoup(html, "lxml")

    stores = []
    for a in soup.select("a.stores-card, a[href*='/en/stores/']"):
        href = a.get("href", "")
        if "/en/stores/" not in href:
            continue
        parts = href.rstrip("/").split("/")
        if len(parts) < 2:
            continue
        full_url = BASE_URL + href if href.startswith("/") else href
        name_el  = a.select_one("h2, h3, .store-name, .card-title")
        name     = clean(name_el.get_text()) if name_el else parts[-1].replace("-", " ").title()
        stores.append({"city": city, "store_name": name, "store_url": full_url})

    return stores


#  SCRAPE PRODUCTS FROM ONE STORE 
def scrape_products(store: dict) -> list[dict]:
    html     = get_html(store["store_url"])
    soup     = BeautifulSoup(html, "lxml")
    products = []

    for card in soup.select(
        "div.product-card, div[class*='product'], article[class*='product']"
    ):
        name_el = card.select_one(
            ".product-card-name, .product-name, h3, h2, [class*='name']"
        )
        if not name_el:
            continue

        name_lines   = [l.strip() for l in name_el.get_text("\n", strip=True).split("\n") if l.strip()]
        product_name = name_lines[0] if name_lines else ""
        size_format  = name_lines[1] if len(name_lines) > 1 else ""
        if not product_name:
            continue

        brand_el = card.select_one(".product-card-brand, .brand, [class*='brand']")
        brand    = clean(brand_el.get_text()) if brand_el else ""

        price_el   = card.select_one(".product-card-price, .price, [class*='price']")
        price_text = clean(price_el.get_text()) if price_el else ""
        prices     = PRICE_RE.findall(price_text)

        regular_price = ""
        sale_price    = ""
        if len(prices) == 1:
            regular_price = prices[0]
        elif len(prices) >= 2:
            vals          = sorted([float(p.replace("$", "").strip()) for p in prices])
            regular_price = f"${vals[-1]:.2f}"
            sale_price    = f"${vals[0]:.2f}"

        promo_duration = "Not listed"
        full_text      = card.get_text(" ", strip=True)
        if PROMO_RE.search(full_text):
            date_m = re.search(
                r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[\w\s,]*\d{1,2}",
                full_text, re.IGNORECASE,
            )
            promo_duration = date_m.group().strip() if date_m else "On sale (end date not listed)"

        products.append({
            "store_name":         store["store_name"],
            "store_city":         store["city"],
            "product_name":       product_name,
            "brand":              brand,
            "size_format":        size_format,
            "regular_price":      regular_price,
            "sale_price":         sale_price,
            "promotion_duration": promo_duration,
            "source_url":         store["store_url"],
        })

    return products


#  MAIN 
def main():
    engine       = get_engine()
    all_stores   = []
    all_products = []

    for city in BBFYB_CITIES:
        print(f"\n--- City: {city} ---")
        try:
            stores = get_store_urls(city)
            print(f"  Found {len(stores)} store(s)")
        except Exception as e:
            print(f"  City page failed: {e}")
            continue

        for store in stores:
            print(f"  Scraping: {store['store_name']}")
            all_stores.append(store)
            try:
                products = scrape_products(store)
                all_products.extend(products)
                print(f"    {len(products)} products")
            except Exception as e:
                print(f"    Failed: {e}")
            time.sleep(DELAY)

    #  Write to PostgreSQL 
    products_df = pd.DataFrame(all_products)
    if products_df.empty:
        print("\nNo products scraped — check if BBFYB site structure changed.")
    else:
        raw_count = len(products_df)

        #  Drop rows where BOTH regular_price and sale_price are missing 
        no_price_mask = (
            products_df["regular_price"].str.strip().eq("") &
            products_df["sale_price"].str.strip().eq("")
        )
        products_df = products_df[~no_price_mask]
        no_price_dropped = raw_count - len(products_df)
        if no_price_dropped:
            print(f"\n  Dropped {no_price_dropped} product(s) with no price info.")

        #  Deduplicate: same store_name + product_name + effective price 
        # Use sale_price when available, else regular_price as the comparison key
        products_df["_price_key"] = products_df["sale_price"].where(
            products_df["sale_price"].str.strip().ne(""),
            products_df["regular_price"],
        )
        before_dedup = len(products_df)
        products_df = products_df.drop_duplicates(
            subset=["store_name", "product_name", "_price_key"]
        )
        products_df = products_df.drop(columns=["_price_key"])
        dedup_dropped = before_dedup - len(products_df)
        if dedup_dropped:
            print(f"  Dropped {dedup_dropped} duplicate product(s) "
                  f"(same store + product name + price).")

        print(f"\n  Final product count to write: {len(products_df)}")
        write_df(products_df, "products_pricing_snapshot", engine, if_exists="replace")

    stores_df = pd.DataFrame(all_stores).drop_duplicates(subset=["store_url"])
    if not stores_df.empty:
        write_df(stores_df, "bbfyb_stores", engine, if_exists="replace")


if __name__ == "__main__":
    main()