# 🌿 MontKailash Cannabis Platform

A full-stack web platform for comparing cannabis product prices and discovering licensed stores within **Burlington, Ontario and a 35 km radius**.

---

## Overview

The platform gives users a live, refreshing view of the Ontario cannabis retail market by:

- Browsing and comparing product prices across multiple licensed stores
- Discovering nearby stores with contact details and hours of operation
- Viewing active deals and promotions
- Searching across products, brands, and stores by keyword

Data is collected automatically from publicly accessible sources via a 3-step scraping pipeline that runs on a configurable schedule (default: every 168 hours / 7 days).

---

## Tech Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| Frontend  | Next.js 14 / React 18               |
| Backend   | Python 3.10+ — FastAPI              |
| Database  | PostgreSQL (`cannabis_db`)          |
| Scheduler | APScheduler (background, interval)  |
| API Docs  | Swagger UI / ReDoc (auto-generated) |

---

## Repository Structure

```
cannabis-platform/
├── frontend/                        # Next.js application
│   ├── components/
│   │   └── Navbar.js                # Site-wide navigation + search bar
│   ├── pages/
│   │   ├── index.js                 # Homepage — stats, featured deals, nearby stores
│   │   ├── deals.js                 # All active deals & promotions
│   │   ├── search.js                # Keyword search results
│   │   ├── products/
│   │   │   ├── index.js             # Product grid with brand/city/price filters
│   │   │   └── [id].js              # Product detail — all stores + prices
│   │   └── stores/
│   │       ├── index.js             # Store listings
│   │       └── [id].js              # Store detail — profile + full product list
│   ├── styles/
│   │   └── globals.css
│   ├── next.config.js               # API_BASE env var forwarded to client
│   └── package.json
│
└── backend/                         # FastAPI application
    ├── main.py                      # All REST API endpoints
    ├── database.py                  # psycopg2 connection pool (FastAPI use)
    ├── scheduler.py                 # APScheduler — auto-runs pipeline every 168 h (7 days)
    ├── requirements.txt
    └── pipeline/                    # Data collection scripts
        ├── fetch_stores_agco.py     # Step 1 — AGCO registry → stores_master
        ├── enrich_store_contacts.py # Step 2 — phone + hours scrape per store
        ├── scrape_competitor_products.py  # Step 3 — BBFYB product & price scrape
        ├── run_all.py               # Manual end-to-end runner
        └── db_config.py             # SQLAlchemy engine + shared DB helpers
```

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python      | 3.10+   |
| Node.js     | 18+     |
| PostgreSQL  | 13+     |

Create the database before running anything:

```bash
createdb cannabis_db
```

---

## Backend Setup

### 1. Navigate to the backend folder

```bash
cd backend
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file inside `backend/` (never commit this file):

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cannabis_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password

# How often the pipeline auto-runs (hours). Default: 168 (7 days)
PIPELINE_INTERVAL_HOURS=168
```

> **Note:** `database.py` currently has hardcoded fallback credentials.
> Always set the environment variables above in production to override them.

### 4. Run the pipeline manually (first-time data load)

```bash
cd pipeline
python run_all.py
```

This runs all 3 steps in sequence and populates `cannabis_db` with stores and product data. Expected runtime: 10–30 minutes depending on network speed.

### 5. Start the FastAPI server

```bash
cd ..          # back to backend/
uvicorn main:app --reload --port 8000
```

| URL | Purpose |
|-----|---------|
| `http://localhost:8000` | API root / health check |
| `http://localhost:8000/docs` | Swagger UI (interactive) |
| `http://localhost:8000/redoc` | ReDoc docs |

---

## Frontend Setup

### 1. Navigate to the frontend folder

```bash
cd frontend
```

### 2. Install dependencies

```bash
npm install
```

### 3. Configure environment variables

Create `.env.local` inside `frontend/`:

```env
API_BASE=http://localhost:8000
```

### 4. Start the development server

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`.

To build for production:

```bash
npm run build
npm run start
```

---

## API Reference

### Stores

| Method | Endpoint                 | Description                                          |
|--------|--------------------------|------------------------------------------------------|
| GET    | `/api/stores`            | List all stores within 35 km of Burlington           |
| GET    | `/api/stores/{store_id}` | Single store detail + all products it carries        |

**Query params — `/api/stores`**

| Param    | Type   | Default | Description              |
|----------|--------|---------|--------------------------|
| `city`   | string | —       | Filter by city name      |
| `limit`  | int    | 100     | Max results (max 500)    |
| `offset` | int    | 0       | Pagination offset        |

### Products

| Method | Endpoint                    | Description                                          |
|--------|-----------------------------|------------------------------------------------------|
| GET    | `/api/products`             | All products with prices — filterable                |
| GET    | `/api/products/{product_id}`| Single product + every store carrying it             |

**Query params — `/api/products`**

| Param       | Type   | Default | Description                  |
|-------------|--------|---------|------------------------------|
| `brand`     | string | —       | Filter by brand name         |
| `city`      | string | —       | Filter by store city         |
| `min_price` | float  | —       | Minimum regular price        |
| `max_price` | float  | —       | Maximum regular price        |
| `limit`     | int    | 100     | Max results (max 1000)       |
| `offset`    | int    | 0       | Pagination offset            |

### Deals, Search & Stats

| Method | Endpoint             | Description                                             |
|--------|----------------------|---------------------------------------------------------|
| GET    | `/api/deals`         | All products currently on sale or promotion             |
| GET    | `/api/search?q=...`  | Keyword search across product names, brands, and stores |
| GET    | `/api/stats`         | Summary counts — stores, products, brands, deals        |

### Pipeline

| Method | Endpoint                  | Description                                          |
|--------|---------------------------|------------------------------------------------------|
| GET    | `/api/pipeline/status`    | Live run state + last persisted run from DB          |
| POST   | `/api/pipeline/run`       | Trigger a full pipeline run in the background        |
| GET    | `/api/pipeline/history`   | Last N pipeline run records with step-level detail   |

---

## Data Pipeline

The backend runs a 3-step scraping pipeline to keep store and product data current.

### Steps

| Step | Script                          | Source                  | Output table                  |
|------|---------------------------------|-------------------------|-------------------------------|
| 1    | `fetch_stores_agco.py`          | AGCO ArcGIS REST API    | `stores_master`               |
| 2    | `enrich_store_contacts.py`      | Individual store sites  | `stores_master` (enriched)    |
| 3    | `scrape_competitor_products.py` | BestBangForYourBud.ca   | `products_pricing_snapshot`   |

### Schedule

The pipeline runs automatically in the background every **168 hours (7 days)** after the FastAPI server starts.

- Default interval: **168 hours (7 days)**
- Override via env var: `PIPELINE_INTERVAL_HOURS=24`
- Manual trigger: `POST /api/pipeline/run`
- Monitor progress: `GET /api/pipeline/status`
- View past runs: `GET /api/pipeline/history`

Run history is persisted to the `pipeline_run_log` table in PostgreSQL.

### Running manually

```bash
cd backend/pipeline
python run_all.py
```

---

## Frontend Pages

| Page             | Route              | Description                                             |
|------------------|--------------------|---------------------------------------------------------|
| Homepage         | `/`                | Stats overview, featured deals, nearby stores, search   |
| Product Listings | `/products`        | Grid view — filter by brand, city, price range          |
| Product Detail   | `/products/[id]`   | Product info + all stores carrying it with prices       |
| Store Listings   | `/stores`          | All stores with address, phone, hours                   |
| Store Detail     | `/stores/[id]`     | Store profile + full product list with current prices   |
| Deals            | `/deals`           | All products currently on sale or promotion             |
| Search           | `/search?q=...`    | Keyword results across products and stores              |

---

## Known Limitations

| Issue | Impact | Recommended Fix |
|-------|--------|-----------------|
| Hardcoded DB credentials in `database.py` | Security risk in production | Move to env vars; use `python-dotenv` |
| `database.py` uses DB name `cannabis`, `db_config.py` uses `cannabis_db` | Connection mismatch if both are used | Align both files to `cannabis_db` |
| Scraper uses `requests` (no JS rendering) | Dynamic/React-based store sites may return empty results | Replace with Playwright for JS-heavy pages |
| No authentication on API or pipeline trigger | `POST /api/pipeline/run` is publicly accessible | Add API key middleware or OAuth |
| `lxml` parser must be installed | BeautifulSoup may silently fall back or error | Explicitly fall back to `html.parser` in scraping steps |

---

## Notes

- All data is sourced from publicly accessible websites and APIs — no paid keys required
- The platform covers Burlington, ON and all licensed stores within a 35 km radius
- No user authentication is required — the platform is read-only and fully public
