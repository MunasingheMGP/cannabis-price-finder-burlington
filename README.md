# Cannabis Price Comparison & Store Discovery Platform

A web platform to compare cannabis product prices and discover licensed stores within **Burlington, Ontario and a 35 km radius**.

---

## Project Overview

This platform allows users to:
- Browse and compare cannabis products by price across multiple licensed stores
- Discover nearby stores with contact details and hours of operation
- View active deals and promotions
- Search across products, brands, and stores by keyword

---

## Tech Stack

| Layer     | Technology                        |
|-----------|-----------------------------------|
| Frontend  | Next.js / React                   |
| Backend   | Python — FastAPI                  |
| Database  | PostgreSQL (`cannabis_db`)        |
| API Docs  | Swagger / OpenAPI (auto-generated)|

---

## Repository Structure

```
cannabis-platform/
├── frontend/                  # Next.js application
│   ├── components/
│   │   └── Navbar.js
│   ├── pages/
│   │   ├── index.js           # Homepage
│   │   ├── deals.js           # Active deals page
│   │   ├── search.js          # Keyword search page
│   │   ├── products/
│   │   │   ├── index.js       # Product listings with filters
│   │   │   └── [id].js        # Product detail page
│   │   └── stores/
│   │       ├── index.js       # Store listings
│   │       └── [id].js        # Store detail page
│   ├── styles/
│   │   └── globals.css
│   ├── next.config.js
│   └── package.json
│
└── backend/                   # FastAPI application
    ├── main.py                # All API endpoints
    ├── database.py            # DB connection helper
    ├── scheduler.py           # Auto-refresh pipeline scheduler
    ├── requirements.txt
    └── pipeline/              # Data pipeline scripts
        ├── fetch_stores_agco.py
        ├── enrich_store_contacts.py
        ├── scrape_competitor_products.py
        ├── run_all.py
        └── db_config.py
```

---

## Prerequisites

- **Node.js** v18 or higher
- **Python** 3.10 or higher
- **PostgreSQL** with the existing `cannabis_db` database

---

## Backend Setup

### 1. Navigate to the backend folder

```bash
cd backend
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set environment variables

Create a `.env` file in the `backend/` folder (or export these variables):

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cannabis_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
PIPELINE_INTERVAL_HOURS=24
```

### 4. Start the FastAPI server

```bash
uvicorn main:app --reload --port 8000
```

The API will be available at: `http://localhost:8000`

Swagger docs: `http://localhost:8000/docs`

ReDoc docs: `http://localhost:8000/redoc`

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

### 3. Set environment variables

Create a `.env.local` file in the `frontend/` folder:

```env
API_BASE=http://localhost:8000
```

### 4. Run the development server

```bash
npm run dev
```

The frontend will be available at: `http://localhost:3000`

---

## API Endpoints

| Method | Endpoint                  | Description                                      |
|--------|---------------------------|--------------------------------------------------|
| GET    | `/api/stores`             | List all stores (name, address, phone, hours)    |
| GET    | `/api/stores/{store_id}`  | Single store + all products it carries           |
| GET    | `/api/products`           | List all products with prices (filterable)       |
| GET    | `/api/products/{id}`      | Single product + all stores carrying it          |
| GET    | `/api/deals`              | All products currently on sale or promotion      |
| GET    | `/api/search?q=keyword`   | Keyword search across products and stores        |
| GET    | `/api/stats`              | Summary counts (stores, products, brands, deals) |
| GET    | `/api/pipeline/status`    | Current data pipeline status                     |
| POST   | `/api/pipeline/run`       | Trigger a manual pipeline refresh                |
| GET    | `/api/pipeline/history`   | Past pipeline run logs                           |

### Filter Parameters — `/api/products`

| Parameter   | Type   | Description                      |
|-------------|--------|----------------------------------|
| `brand`     | string | Filter by brand name             |
| `city`      | string | Filter by store city             |
| `min_price` | float  | Minimum regular price            |
| `max_price` | float  | Maximum regular price            |
| `limit`     | int    | Max results (default 100)        |
| `offset`    | int    | Pagination offset (default 0)    |

---

## Pages

| Page              | Route              | Description                                      |
|-------------------|--------------------|--------------------------------------------------|
| Homepage          | `/`                | Featured deals, nearby stores, stats, search bar |
| Product Listings  | `/products`        | Browsable grid — filter by category, brand, city, price |
| Product Detail    | `/products/[id]`   | Product info, prices, and all stores carrying it |
| Store Listings    | `/stores`          | All stores with name, address, phone, hours      |
| Store Detail      | `/stores/[id]`     | Store profile + full product list with prices    |
| Deals             | `/deals`           | Products currently on sale or promotion          |
| Search            | `/search?q=...`    | Keyword search results (products + stores)       |

---

## Data Pipeline

The backend includes an automated data pipeline that refreshes store and product data:

- **Auto-runs** every 24 hours (configurable via `PIPELINE_INTERVAL_HOURS`)
- **Manual trigger**: `POST /api/pipeline/run`
- **Check status**: `GET /api/pipeline/status`
- **View history**: `GET /api/pipeline/history`

Pipeline steps:
1. Fetch stores from AGCO registry
2. Enrich store contacts
3. Scrape competitor product prices
4. Compare market prices
5. Reddit sentiment analytics
6. Score product insights

---

## Team Members

- Add team member names and GitHub usernames here

---

## Notes

- No authentication is required — the platform is fully public
- All prices and store data are sourced from the existing `cannabis_db` database
- The platform covers Burlington, ON and stores within a 35 km radius

