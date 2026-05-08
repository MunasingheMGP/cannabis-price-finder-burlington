"""
Run the full MontKailash pipeline end to end.
All intermediate and final data stored in PostgreSQL (cannabis_db).
"""

import subprocess
import sys
import time
from pathlib import Path
from db_config import get_engine
from sqlalchemy import text

STEPS = [
    ("fetch_stores_agco.py",          "Fetching licensed stores from AGCO registry"),
    ("enrich_store_contacts.py",       "Enriching stores with phone numbers and hours"),
    ("scrape_competitor_products.py",  "Scraping competitor products and pricing"),
]

# Tables created by each step (for post-run summary)
STEP_TABLES = {
    "fetch_stores_agco.py":          ["stores_master"],
    "enrich_store_contacts.py":      ["stores_master"],
    "scrape_competitor_products.py": ["products_pricing_snapshot", "bbfyb_stores"],
}


def verify_db_connection():
    """Fail fast if PostgreSQL is unreachable."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  DB connection OK (cannabis_db @ localhost:5432)\n")
    except Exception as e:
        print(f"\nCannot connect to PostgreSQL: {e}")
        print("  Make sure PostgreSQL is running and cannabis_db exists.")
        print("  Quick fix:  createdb cannabis_db")
        sys.exit(1)


def run_step(script: str, description: str, step_num: int, total: int):
    print(f"\n{'='*60}")
    print(f"  Step {step_num}/{total} — {description}")
    print(f"  Running: {script}")
    print(f"{'='*60}")

    start  = time.time()
    result = subprocess.run([sys.executable, script], check=False)
    elapsed = round(time.time() - start, 1)

    if result.returncode != 0:
        print(f"\nStep {step_num} FAILED ({script}) after {elapsed}s")
        print("  Fix the error above and re-run from this step.")
        sys.exit(result.returncode)

    print(f"\nStep {step_num} done in {elapsed}s")


def print_db_summary():
    """Print row counts for all pipeline tables after completion."""
    engine = get_engine()
    all_tables = [
        "stores_master",
        "products_pricing_snapshot",
        "bbfyb_stores",
    ]
    print("\n  PostgreSQL table summary (cannabis_db):")
    print(f"  {'Table':<40} {'Rows':>8}")
    print(f"  {'-'*40} {'-'*8}")
    with engine.connect() as conn:
        for t in all_tables:
            try:
                count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
                print(f"  {t:<40} {count:>8,}")
            except Exception:
                print(f"  {t:<40} {'(missing)':>8}")


def main():
    print("\n MontKailash Cannabis — Full Pipeline")
    print(f"    {len(STEPS)} steps | Data -> PostgreSQL cannabis_db\n")

    verify_db_connection()

    missing = [s for s, _ in STEPS if not Path(s).exists()]
    if missing:
        print("Missing script files:")
        for m in missing:
            print(f"    - {m}")
        sys.exit(1)

    total_start = time.time()

    for i, (script, description) in enumerate(STEPS, 1):
        run_step(script, description, i, len(STEPS))

    total = round(time.time() - total_start, 1)
    print(f"\n{'='*60}")
    print(f"  All {len(STEPS)} steps completed in {total}s")
    print_db_summary()
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()