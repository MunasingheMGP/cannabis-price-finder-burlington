"""
Enrich stores_master table with real phone numbers
and hours scraped from each store's own website.
Reads from / writes back to PostgreSQL.
"""

import re
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from db_config import get_engine, read_df, write_df

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 15
DELAY   = 1.2

PHONE_RE = re.compile(
    r"(\+?1[\s\-.]?)?"
    r"\(?\d{3}\)?[\s\-.]"
    r"\d{3}[\s\-.]"
    r"\d{4}"
)

HOURS_SIGNALS = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "hours of operation", "store hours", "open daily",
]

DAY_ABBR = r"(mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
HOURS_LINE_RE = re.compile(
    DAY_ABBR + r".*?(\d{1,2}(:\d{2})?\s*(am|pm))",
    re.IGNORECASE,
)


#  EXTRACT PHONE 
def extract_phone(text: str) -> str:
    for m in PHONE_RE.finditer(text):
        phone  = m.group().strip()
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 10:
            return phone
    return "Not listed"


#  EXTRACT HOURS 
def extract_hours(soup: BeautifulSoup, raw_text: str) -> str:
    for tag in soup.find_all(
        ["div", "section", "ul", "p", "table"],
        class_=re.compile(r"hour|schedule|time|open", re.I),
    ):
        chunk = tag.get_text(" ", strip=True)
        if any(s in chunk.lower() for s in HOURS_SIGNALS):
            return re.sub(r"\s{2,}", " ", chunk)[:300]

    found_lines = []
    for line in raw_text.splitlines():
        if HOURS_LINE_RE.search(line):
            found_lines.append(line.strip())
        if len(found_lines) >= 7:
            break
    if found_lines:
        return " | ".join(found_lines)[:300]

    for p in soup.find_all(["p", "span", "li"]):
        t = p.get_text(" ", strip=True).lower()
        if any(s in t for s in HOURS_SIGNALS) and len(t) < 500:
            return p.get_text(" ", strip=True)[:300]

    return "Not listed"


#  SCRAPE ONE STORE URL 
def scrape_store(url: str):
    phone = "Not listed"
    hours = "Not listed"

    if not url or str(url).strip().lower() in ("nan", "", "none", "not listed"):
        return phone, hours

    if not url.startswith("http"):
        url = "https://" + url

    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        raw   = soup.get_text("\n", strip=True)
        phone = extract_phone(raw)
        hours = extract_hours(soup, raw)

        if hours == "Not listed":
            for suffix in ["/contact", "/contact-us", "/about", "/store-info"]:
                try:
                    base = url.rstrip("/")
                    r2   = requests.get(base + suffix, headers=HEADERS,
                                        timeout=TIMEOUT, allow_redirects=True)
                    if r2.status_code == 200:
                        soup2 = BeautifulSoup(r2.text, "lxml")
                        for t in soup2(["script", "style"]):
                            t.decompose()
                        raw2  = soup2.get_text("\n", strip=True)
                        if phone == "Not listed":
                            phone = extract_phone(raw2)
                        hours = extract_hours(soup2, raw2)
                        if hours != "Not listed":
                            break
                except Exception:
                    pass

    except Exception as e:
        print(f"    ⚠  Could not scrape {url}: {e}")

    return phone, hours


#  MAIN 
def main():
    engine = get_engine()
    df     = read_df("stores_master", engine)
    total  = len(df)
    print(f"Enriching {total} stores with phone + hours...\n")

    phones     = []
    hours_list = []

    for i, row in df.iterrows():
        store = row.get("store_name", f"Store {i}")
        url   = str(row.get("website", "")).strip()

        print(f"[{i+1}/{total}] {store} — {url or 'no website'}")
        phone, hours = scrape_store(url)
        print(f"    Phone : {phone}")
        print(f"    Hours : {hours[:80]}{'...' if len(hours) > 80 else ''}")

        phones.append(phone)
        hours_list.append(hours)
        time.sleep(DELAY)

    df["phone_number"]       = phones
    df["hours_of_operation"] = hours_list

    #  Write enriched data back to PostgreSQL 
    write_df(df, "stores_master", engine, if_exists="replace")

    filled_phone = sum(1 for p in phones if p != "Not listed")
    filled_hours = sum(1 for h in hours_list if h != "Not listed")
    print(f"\nPhone found : {filled_phone}/{total}")
    print(f"Hours found : {filled_hours}/{total}")


if __name__ == "__main__":
    main()
