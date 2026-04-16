**Admin Reports — Sales Dashboard**

This document describes the design and implementation of the Admin "Report" feature (sales dashboard) implemented in this repository. It covers architecture, end‑to‑end data flow, key components, frontend state management, configuration and runtime dependencies, testing and verification steps, and suggested improvements.

- **Where implemented (core files):**
  - Frontend UI: `frontend/src/views/admin/AdminReports.vue`
  - Frontend HTTP client: `frontend/src/api/http.ts`
  - Backend report endpoint: `backend/app/routers/admin.py` (route: `GET /api/admin/reports/sales`)
  - Backend response schema: `backend/app/schemas.py` (`SalesSummaryOut`, `SalesSeriesPoint`, `BestSellerOut`)
  - Admin auth dependency: `backend/app/deps.py` (`get_current_admin`)

Overview
--------

Purpose: provide administrators a compact dashboard for observing sales activity over time and identifying top selling products. The current V1 dashboard supports:

- selecting a date range and granularity (day / week / month)
- a sales trend chart (sales amount line + order count bars)
- a top‑N best sellers horizontal bar chart
- simple summary stats (total sales, order count)

The feature is intentionally read‑only and gated behind admin authentication.

Architecture & responsibilities
------------------------------

- Frontend (single component)
  - `frontend/src/views/admin/AdminReports.vue` contains the entire admin report UI, including form controls, chart rendering and local state. It uses Element Plus components for UI and ECharts for charting.
  - The component fetches data from the backend via the axios wrapper `frontend/src/api/http.ts` which applies JWT from `localStorage` and handles 401/403 globally.

- Backend (single report endpoint)
  - `backend/app/routers/admin.py` implements `GET /api/admin/reports/sales`. It is protected by `get_current_admin` and `get_db` dependencies. The endpoint queries Orders/OrderItems/ProductSKU/Product to build the response defined in `backend/app/schemas.py`.

- Data model & schema
  - Response model: `SalesSummaryOut` (see `backend/app/schemas.py`) contains `total_sales`, `order_count`, `best_sellers[]`, and a `series[]` with `SalesSeriesPoint` entries (`period`, `sales`, `order_count`).

Data flow (end‑to‑end)
---------------------

1. Admin opens Admin Reports page (`/admin/reports`). Router guards require admin access (`requiresAdmin: true`) — routing entry in `frontend/src/router/index.ts`.
2. The page initializes a `form.range` (default last 30 days) and `form.granularity` ('day' by default).
3. User clicks Search; frontend constructs query parameters `{ start, end, granularity }` and calls `api.get('/api/admin/reports/sales', { params })` (see `AdminReports.vue::load`).
4. The request includes `Authorization: Bearer <JWT>` header because `frontend/src/api/http.ts` attaches `token` from `localStorage`.
5. Backend `GET /api/admin/reports/sales` authenticates the caller via `get_current_admin` (`backend/app/deps.py`) and then:
   - parses/validates `start` / `end` dates and `granularity` ('day'|'week'|'month')
   - queries `models.Order` for non‑cancelled orders inside the date range
   - computes `total_sales` and `order_count` (sum and count)
   - aggregates orders into time buckets (period) according to `granularity` and builds `series`
   - computes `best_sellers` by joining `OrderItem` → `ProductSKU` → `Product` and summing `quantity * unit_price`, limited to top 10
   - returns a JSON shaped as `SalesSummaryOut`.
6. Frontend receives response and stores it in component state `summary` and derived computed arrays. After `nextTick()` it renders ECharts options using the data.

Key frontend implementation details
----------------------------------

- Component structure
  - `form` (reactive `ref`) holds `range: [start, end]` and `granularity`.
  - `summary` (reactive `ref`) stores the server response object.
  - `trendEl` / `bestEl` (refs) are DOM targets for ECharts instances.
  - `trendChart` / `bestChart` are module variables that hold ECharts instances to avoid reinitializing across renders.
  - Computed helpers transform `summary` into arrays used by ECharts: `trendPeriods`, `trendSales`, `trendOrders`, `bestNames`, `bestSales`.

- Rendering lifecycle
  - `load()` fetches data and assigns `summary.value = data`.
  - After assignment the component calls `renderCharts()` which:
    - ensures ECharts instances are created (`echarts.init`) and
    - calls `setOption()` on both charts with the derived series and legend/axis configuration.
  - The component listens to `window.resize` to call `.resize()` on the charts.

- UI & i18n
  - UI built with Element Plus (`el-card`, `el-statistic`, `el-form`, `el-date-picker`, `el-select`).
  - `useI18n()` is used to render strings. The chart titles/legends are also re-rendered on locale change by watching `locale` and calling `renderCharts()`.

Key backend implementation details
---------------------------------

- Endpoint: `GET /api/admin/reports/sales` implemented in `backend/app/routers/admin.py`.
- Authentication: decorated with `admin=Depends(get_current_admin)`, which raises HTTP 403 if the caller is not an admin (`backend/app/deps.py`).
- Input parsing: `start`/`end` are `YYYY-MM-DD` strings; when absent defaults to last 30 days (China time via `now_cn_naive`).
- Data selection: orders with `status != 'cancelled'` and `created_at` within the inclusive date range.
- Aggregation:
  - Orders are fetched into memory and aggregated into a `series_map` in Python (period -> {sales, order_count}).
  - `best_sellers` are computed with a SQL JOIN / GROUP BY over `Product`, `ProductSKU`, `OrderItem`, and `Order`, filtered by the set of selected `order_id`s and limited to top 10.
- Output: `schemas.SalesSummaryOut` (Pydantic model) is returned.

State management & concurrency
-----------------------------

- Frontend state is local to `AdminReports.vue` (no Pinia/Vuex used). This keeps the component isolated and simple.
- The backend endpoint is read‑only relative to order data (no concurrent writes from this endpoint). The endpoint may still read rows that are being updated by order transitions; business logic assumes eventual consistency for reporting.

Configuration & runtime dependencies
-----------------------------------

- Frontend
  - `frontend/package.json` dependencies used by this page: `axios`, `echarts`, `element-plus`, `vue`, `vue-i18n`, `vue-router`.
  - Base API URL: environment variable `VITE_API_BASE_URL` (fallback `http://localhost:8001`) — configured in `frontend/src/api/http.ts`.

- Backend
  - FastAPI, SQLAlchemy, and Pydantic are used (see `backend/requirements.txt` if present).
  - Admin auth uses JWT decoding logic in `backend/app/auth.py` and `backend/app/deps.py`.
  - Time handling uses `backend/app/time_utils.py` with China‑timezone helpers (the report endpoint uses `now_cn_naive` to compute default ranges).

Security & access control
------------------------

- The report endpoint is protected by `get_current_admin` which returns 403 if `current_user.is_admin` is false. The frontend attaches the JWT from `localStorage` automatically; `frontend/src/api/http.ts` redirects to login on 401 and shows a message on 403.

API contract and examples
-------------------------

Request (GET):

```
GET /api/admin/reports/sales?start=2026-03-01&end=2026-03-31&granularity=day
Authorization: Bearer <JWT>
```

Response (200, example shape):

```json
{
  "total_sales": 12345.67,
  "order_count": 321,
  "best_sellers": [
    { "product_id": 10, "title": "Book A", "title_en": "Book A EN", "sales": 2345.5 }
  ],
  "series": [
    { "period": "2026-03-01", "sales": 123.4, "order_count": 5 },
    { "period": "2026-03-02", "sales": 99.2, "order_count": 3 }
  ]
}
```

Sample curl (requires a valid admin token):

```bash
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8001/api/admin/reports/sales?start=2026-03-01&end=2026-03-31&granularity=day"
```

Testing and verification
------------------------

1. Start backend dev server (typical):

```bash
# from repo root
uvicorn backend.app.main:app --reload --port 8001
```

2. Start frontend dev server:

```bash
cd frontend
npm install
npm run dev
# open http://localhost:5173 and login as admin
```

3. Navigate to Admin → Reports (`/admin/reports`), choose a date range and click Search. Verify charts update and summary values match backend data.

4. For backend unit tests, add tests that call `GET /api/admin/reports/sales` with different ranges and granularities using a test DB seeded via `backend/app/seed.py`.

Known limitations & recommended improvements
------------------------------------------

- Current backend aggregates orders in Python after loading all matching rows into memory (see comment in `backend/app/routers/admin.py`: "For simplicity this uses Python aggregation"). This implementation is fine for small datasets but will not scale to production volumes.

  Recommendations:

  1. Move aggregation into the database (GROUP BY on date_trunc or equivalent) rather than loading all rows into memory. Use SQL functions or SQLAlchemy expression to perform time bucketing.
  2. Add proper indexes on `orders.created_at`, `orders.status`, `order_items.sku_id` to speed up joins and filters.
  3. Introduce a periodic job (cron / background worker) to precompute daily rollups or materialized views if real‑time reporting is not required.
  4. Add CSV / Excel export endpoint and pagination for `best_sellers` if the catalog is large.

- Timezone handling: the API assumes China local date semantics (`now_cn_naive`) for default ranges and parsing. If the system will be used in multi‑timezone scenarios, add an explicit timezone parameter or accept full ISO timestamps.

- Filtering & drilldowns: consider adding filters (by category, vendor, product id, SKU, region) and additional metrics (average order value, return rate, refunds), and enable clicking on a bar to drill into orders for that period.

Operational notes
-----------------

- Logs: `backend/app/routers/admin.py` logs some admin operations (product search). Consider adding a log line for report queries that includes user id and parameters (beware of PII).
- Rate limits: if the admin UI will be used heavily, add rate limiting or caching on the report endpoint to avoid expensive repeated aggregations.

Files referenced
----------------

- `frontend/src/views/admin/AdminReports.vue` — UI, charts and client logic
- `frontend/src/api/http.ts` — axios wrapper, JWT injection, 401/403 behavior
- `frontend/src/router/index.ts` — route registration (`/admin/reports`, requiresAdmin meta)
- `frontend/src/i18n/*.json` — localized strings used by the page
- `backend/app/routers/admin.py` — `GET /api/admin/reports/sales` implementation
- `backend/app/schemas.py` — `SalesSummaryOut`, `SalesSeriesPoint`, `BestSellerOut`
- `backend/app/deps.py` — `get_current_admin` admin guard

Next actionable items (prioritized)
----------------------------------

1. Move aggregation logic into SQL and add DB indexes (`orders.created_at`, `orders.status`, `order_items.sku_id`) — improves performance for larger datasets.
2. Add a CSV export endpoint and a frontend "Export" button in `AdminReports.vue`.
3. Add server‑side caching or precomputed daily rollups to reduce load for repeated queries.
4. Support drilldown filters (category, product, SKU, customer) and pagination for `best_sellers`.

This document provides a single‑place technical reference for the Admin Reports feature implemented in the repository. It is intended to help maintainers understand current implementation choices and to serve as a starting point for scaling and feature extension.
