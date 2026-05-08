"""
Cannabis Price Comparison & Store Discovery Platform
Backend API — FastAPI + PostgreSQL (cannabis_db)
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from database import get_connection
from typing import Optional
import re

# ── Make pipeline/ importable ─────────────────────────────────────────────────
PIPELINE_DIR = Path(__file__).parent / "pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

from scheduler import (
    start_scheduler, stop_scheduler,
    run_pipeline, pipeline_state, get_last_run_from_db,
)

# ── Pipeline schedule: hours between automatic runs (default 24) ──────────────
PIPELINE_INTERVAL_HOURS = int(os.getenv("PIPELINE_INTERVAL_HOURS", "24"))


# ── Lifespan: start scheduler on boot, stop on shutdown ──────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    from db_config import get_engine
    engine = get_engine()
    start_scheduler(engine, interval_hours=PIPELINE_INTERVAL_HOURS)
    yield
    stop_scheduler()


app = FastAPI(
    title="Cannabis Platform API",
    description="Price comparison & store discovery for Burlington, ON (35 km radius)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── HELPERS ────────────────────────────────────────────────────────────────────

def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def store_slug(store: dict) -> str:
    """Unique store ID combining store_name + postal_code to avoid collisions
    when multiple stores share the same name (e.g. two 'TreeTop' locations)."""
    return slug(str(store.get("store_name", "")) + "-" + str(store.get("postal_code", "")))


def rows_to_list(cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ── ROOT ───────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Cannabis Platform API is running"}


# ── STORES ─────────────────────────────────────────────────────────────────────

@app.get("/api/stores", tags=["Stores"], summary="List all stores")
def list_stores(
    city: Optional[str] = Query(None, description="Filter by city name"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Returns all licensed cannabis stores within 35 km of Burlington, ON.
    Includes name, address, phone, hours, and owner details.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        base = """
            SELECT
                store_name, address, city, postal_code,
                phone_number, hours_of_operation,
                owner_details, website,
                ROUND(distance_km::numeric, 2) AS distance_km
            FROM stores_master
        """
        if city:
            cur.execute(base + " WHERE LOWER(city) = LOWER(%s) ORDER BY distance_km LIMIT %s OFFSET %s",
                        (city, limit, offset))
        else:
            cur.execute(base + " ORDER BY distance_km LIMIT %s OFFSET %s", (limit, offset))

        stores = rows_to_list(cur)

    for s in stores:
        s["id"] = store_slug(s)
    return {"total": len(stores), "stores": stores}


@app.get("/api/stores/{store_id}", tags=["Stores"], summary="Store detail with products")
def store_detail(store_id: str):
    """
    Returns full details for a single store plus all products it currently carries with prices.
    """
    with get_connection() as conn:
        cur = conn.cursor()

        # fetch store
        cur.execute("""
            SELECT store_name, address, city, postal_code,
                   phone_number, hours_of_operation,
                   owner_details, website,
                   ROUND(distance_km::numeric, 2) AS distance_km
            FROM stores_master
        """)
        all_stores = rows_to_list(cur)
        store = next((s for s in all_stores if store_slug(s) == store_id), None)
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")

        # fetch products for this store
        cur.execute("""
            SELECT product_name, brand, size_format,
                   regular_price, sale_price, promotion_duration
            FROM products_pricing_snapshot
            WHERE LOWER(store_name) = LOWER(%s)
            ORDER BY product_name
        """, (store["store_name"],))
        products = rows_to_list(cur)

    store["id"]       = store_id
    store["products"] = products
    return store


# ── PRODUCTS ───────────────────────────────────────────────────────────────────

@app.get("/api/products", tags=["Products"], summary="List all products")
def list_products(
    brand: Optional[str]    = Query(None, description="Filter by brand"),
    city: Optional[str]     = Query(None, description="Filter by store city"),
    min_price: Optional[float] = Query(None, description="Minimum regular price"),
    max_price: Optional[float] = Query(None, description="Maximum regular price"),
    limit: int  = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Returns all products with regular price, sale price, promotion duration, and store info.
    Supports filtering by brand, city, and price range.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        where_clauses = []
        params: list = []

        if brand:
            where_clauses.append("LOWER(brand) LIKE LOWER(%s)")
            params.append(f"%{brand}%")
        if city:
            where_clauses.append("LOWER(store_city) = LOWER(%s)")
            params.append(city)
        if min_price is not None:
            where_clauses.append(
                "REPLACE(REPLACE(regular_price,'$',''),',','')::numeric >= %s"
            )
            params.append(min_price)
        if max_price is not None:
            where_clauses.append(
                "REPLACE(REPLACE(regular_price,'$',''),',','')::numeric <= %s"
            )
            params.append(max_price)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        params += [limit, offset]

        cur.execute(f"""
            SELECT p.store_name, p.store_city, p.product_name, p.brand,
                   p.size_format, p.regular_price, p.sale_price, p.promotion_duration,
                   COALESCE(sm.postal_code, '') AS postal_code
            FROM products_pricing_snapshot p
            LEFT JOIN stores_master sm ON LOWER(sm.store_name) = LOWER(p.store_name)
            {where_sql}
            ORDER BY p.product_name, p.store_name
            LIMIT %s OFFSET %s
        """, params)

        products = rows_to_list(cur)

    for p in products:
        p["id"]       = slug(p["product_name"])
        p["store_id"] = slug(str(p.get("store_name", "")) + "-" + str(p.get("postal_code", "")))
        p["on_sale"]  = bool(p.get("sale_price"))

    return {"total": len(products), "products": products}


@app.get("/api/products/{product_id}", tags=["Products"], summary="Product detail with all stores")
def product_detail(product_id: str):
    """
    Returns full product info and every store currently carrying it with their prices.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.store_name, p.store_city, p.product_name, p.brand,
                   p.size_format, p.regular_price, p.sale_price, p.promotion_duration,
                   COALESCE(sm.postal_code, '') AS postal_code
            FROM products_pricing_snapshot p
            LEFT JOIN stores_master sm ON LOWER(sm.store_name) = LOWER(p.store_name)
            ORDER BY p.product_name
        """)
        all_rows = rows_to_list(cur)

    matches = [r for r in all_rows if slug(r["product_name"]) == product_id]
    if not matches:
        raise HTTPException(status_code=404, detail="Product not found")

    first = matches[0]
    stores_carrying = [
        {
            "store_id":         slug(str(r["store_name"]) + "-" + str(r.get("postal_code", ""))),
            "store_name":       r["store_name"],
            "store_city":       r["store_city"],
            "regular_price":    r["regular_price"],
            "sale_price":       r["sale_price"],
            "promotion_duration": r["promotion_duration"],
        }
        for r in matches
    ]

    return {
        "id":               product_id,
        "product_name":     first["product_name"],
        "brand":            first["brand"],
        "size_format":      first["size_format"],
        "stores":           stores_carrying,
        "store_count":      len(stores_carrying),
        "lowest_price":     min(
            (r["regular_price"] for r in matches if r["regular_price"]),
            default=None
        ),
    }


# ── DEALS ──────────────────────────────────────────────────────────────────────

@app.get("/api/deals", tags=["Deals"], summary="Products currently on sale")
def list_deals(
    city: Optional[str] = Query(None, description="Filter by store city"),
    limit: int  = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Returns all products currently on sale or promotion, with duration where available.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        base = """
            SELECT p.store_name, p.store_city, p.product_name, p.brand,
                   p.size_format, p.regular_price, p.sale_price, p.promotion_duration,
                   COALESCE(sm.postal_code, '') AS postal_code
            FROM products_pricing_snapshot p
            LEFT JOIN stores_master sm ON LOWER(sm.store_name) = LOWER(p.store_name)
            WHERE p.sale_price IS NOT NULL AND p.sale_price != ''
        """
        if city:
            cur.execute(base + " AND LOWER(p.store_city) = LOWER(%s) ORDER BY p.product_name LIMIT %s OFFSET %s",
                        (city, limit, offset))
        else:
            cur.execute(base + " ORDER BY p.product_name LIMIT %s OFFSET %s", (limit, offset))

        deals = rows_to_list(cur)

    for d in deals:
        d["id"]       = slug(d["product_name"])
        d["store_id"] = slug(str(d.get("store_name", "")) + "-" + str(d.get("postal_code", "")))

    return {"total": len(deals), "deals": deals}


# ── SEARCH ─────────────────────────────────────────────────────────────────────

@app.get("/api/search", tags=["Search"], summary="Keyword search across products and stores")
def search(
    q: str = Query(..., min_length=2, description="Search keyword"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Searches products (by name, brand) and stores (by name, city, address) in one call.
    Returns matched products and matched stores separately.
    """
    term = f"%{q}%"
    with get_connection() as conn:
        cur = conn.cursor()

        # product search
        cur.execute("""
            SELECT DISTINCT product_name, brand, size_format,
                            regular_price, sale_price
            FROM products_pricing_snapshot
            WHERE LOWER(product_name) LIKE LOWER(%s)
               OR LOWER(brand) LIKE LOWER(%s)
            ORDER BY product_name
            LIMIT %s
        """, (term, term, limit))
        products = rows_to_list(cur)

        # store search
        cur.execute("""
            SELECT store_name, address, city, postal_code,
                   phone_number, hours_of_operation, website
            FROM stores_master
            WHERE LOWER(store_name) LIKE LOWER(%s)
               OR LOWER(city) LIKE LOWER(%s)
               OR LOWER(address) LIKE LOWER(%s)
            ORDER BY store_name
            LIMIT %s
        """, (term, term, term, limit))
        stores = rows_to_list(cur)

    for p in products:
        p["id"] = slug(p["product_name"])
    for s in stores:
        s["id"] = store_slug(s)

    return {
        "query":    q,
        "products": products,
        "stores":   stores,
        "total_products": len(products),
        "total_stores":   len(stores),
    }


# ── STATS (bonus) ──────────────────────────────────────────────────────────────

@app.get("/api/stats", tags=["Stats"], summary="Platform summary stats")
def stats():
    """Quick summary numbers for the homepage dashboard."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM stores_master")
        store_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT product_name) FROM products_pricing_snapshot")
        product_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT brand) FROM products_pricing_snapshot WHERE brand != ''")
        brand_count = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM products_pricing_snapshot
            WHERE sale_price IS NOT NULL AND sale_price != ''
        """)
        deals_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT city) FROM stores_master")
        city_count = cur.fetchone()[0]

    return {
        "stores":   store_count,
        "products": product_count,
        "brands":   brand_count,
        "deals":    deals_count,
        "cities":   city_count,
    }


# ── PIPELINE ───────────────────────────────────────────────────────────────────

@app.get("/api/pipeline/status", tags=["Pipeline"],
         summary="Current pipeline status and last run details")
def pipeline_status():
    """
    Returns the live pipeline_state dict (if a run is in progress or just
    finished) plus the most recent persisted run record from the DB.
    """
    from db_config import get_engine
    engine = get_engine()
    last_db = get_last_run_from_db(engine)
    return {
        "live":    pipeline_state,
        "last_db": last_db,
        "schedule_interval_hours": PIPELINE_INTERVAL_HOURS,
    }


@app.post("/api/pipeline/run", tags=["Pipeline"],
          summary="Trigger a full pipeline run manually")
def trigger_pipeline(background_tasks: BackgroundTasks):
    """
    Kicks off the full 6-step data pipeline in the background.
    Returns immediately with a 202 accepted response.
    Poll /api/pipeline/status to track progress.
    """
    if pipeline_state.get("status") == "running":
        raise HTTPException(status_code=409,
                            detail="Pipeline is already running. Check /api/pipeline/status.")

    from db_config import get_engine
    engine = get_engine()
    background_tasks.add_task(run_pipeline, engine)

    return {
        "accepted": True,
        "message":  "Pipeline started in background. Poll /api/pipeline/status for progress.",
        "steps":    [
            "fetch_stores_agco",
            "enrich_store_contacts",
            "scrape_competitor_products",
            "compare_market_prices",
            "reddit_sentiment_analytics",
            "score_product_insights",
        ],
    }


@app.get("/api/pipeline/history", tags=["Pipeline"],
         summary="Last N pipeline run records from the database")
def pipeline_history(limit: int = Query(10, ge=1, le=100)):
    """Returns the most recent pipeline runs with timing and step results."""
    import json
    from db_config import get_engine
    engine = get_engine()
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, run_started_at, run_finished_at,
                       status, steps_json, error_message
                FROM pipeline_run_log
                ORDER BY id DESC
                LIMIT :lim
            """), {"lim": limit}).fetchall()

        history = []
        for r in rows:
            history.append({
                "id":              r[0],
                "run_started_at":  r[1].isoformat() if r[1] else None,
                "run_finished_at": r[2].isoformat() if r[2] else None,
                "status":          r[3],
                "steps":           json.loads(r[4]) if r[4] else [],
                "error_message":   r[5],
            })
        return {"total": len(history), "runs": history}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))