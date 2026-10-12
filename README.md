# Climate Hazard Trend Analyzer

A web app that analyzes historical daily weather for a selected region and shows how
climate hazards have changed over time. Heatwave is the default (and currently only) hazard.

> **Status:** Phases 0–4 of the implementation plan are scaffolded and run end to end
> against synthetic data. Not yet done: live check against Open-Meteo, MongoDB Atlas,
> deployment, Leaflet map, PDF export, drought/rainfall. Sections marked **TODO** get filled
> in as the build progresses.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript |
| Charts | Chart.js via `react-chartjs-2` |
| Client cache | TanStack Query (1 h stale time) |
| Backend | FastAPI (Python 3.11+) |
| HTTP client | `httpx` + `tenacity` (timeouts, retries with backoff + jitter) |
| Analysis | `pandas`, `numpy`, `scipy`, `pymannkendall` |
| Rate limiting | `slowapi` (per IP) |
| Database | MongoDB (Atlas M0 or local) via PyMongo's native async client |
| Hosting | Vercel (frontend), Render (backend) — **TODO** |

> Deviation from the plan: the plan named `motor`. Motor is deprecated in favour of PyMongo's
> built-in async API (`AsyncMongoClient`), so the backend uses that instead. Same driver
> team, near-identical API.

## Architecture

```
React (Vite)  ──HTTPS JSON──▶  FastAPI  (validate · rate-limit · analyze)
                                  │
             1. analysis cache ───┼──▶ hazard_results  (MongoDB)
             2. raw daily cache ──┼──▶ weather_daily   (MongoDB, one doc per cell-year)
             3. fetch on miss ────┴──▶ Open-Meteo archive API (ERA5)
```

Request flow for `GET /api/hazards/heatwave`:

1. Validate query params with Pydantic; anything invalid → 422.
2. Snap coordinates to the ERA5 0.25° grid → cell key.
3. Result key = `sha256(cells, hazard, baseline, range, params, ALGO_VERSION)`.
4. If the key is in `hazard_results`, return it (`"cache": "hit"`).
5. Otherwise load baseline years ∪ requested years for each cell from `weather_daily`;
   fetch only missing years from Open-Meteo (one fetch per cell at a time, coalesced with a
   per-cell `asyncio.Lock`), clean, store.
6. Run the hazard engine in a worker thread, store the result, return it.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness; also wakes a sleeping Render instance |
| GET | `/api/regions` | Preset cities and areas for Andhra Pradesh and Telangana |
| GET | `/api/geocode?q=pune` | City search via Open-Meteo, cached in-process (24 h) |
| GET | `/api/hazards` | Available hazards and defaults |
| GET | `/api/hazards/{hazard}?lat=&lon=&start=&end=` | Analysis for a point |
| GET | `/api/hazards/{hazard}?bbox=minLon,minLat,maxLon,maxLat&start=&end=` | Analysis for a box (≤ 2°×2°, ≤ 25 sampled cells) |
| GET | `/api/hazards/{hazard}/export.csv?...` | Yearly metrics as CSV |

Optional params: `percentile` (90–99, default 95), `min_days` (2–7, default 3),
`threshold_mode` (`annual` only for now).

Errors always look like `{"error": {"code": "VALIDATION_ERROR", "message": "..."}}`.
Status codes: 422 validation, 404 unknown hazard, 429 rate-limited, 502/504 upstream failure/timeout.

Interactive docs: `http://localhost:8000/docs`.

## Hazard logic: heatwave

3+ consecutive days with daily Tmax above the 95th percentile of the **fixed 1991–2020
baseline** (annual threshold). Code: `backend/app/hazards/heatwave.py`.

- Threshold depends only on the baseline, so changing the year range never moves it.
- A missing day ends a run (no event is invented across gaps).
- An event belongs to the year it **starts** (an event crossing Dec 31 counts once).
- Years with < 95% of days present are excluded from trends and flagged.
- Per event: `peak_tmax`, `mean_exceedance`, `excess_heat` (°C·days above threshold).
- Per year: `event_count`, `heatwave_days`, `mean_duration`, `max_duration`,
  `mean_intensity`, `peak_tmax`, `excess_heat`.

## Trend and insight

- Theil–Sen slope (per decade) + Mann-Kendall test (α = 0.05); OLS as a reference.
- 5-year centred rolling mean, for display only.
- Insight sentence rules (`backend/app/stats/insight.py`): compare first-decade vs
  last-decade means (trend line endpoints if range < 20 years); absolute change when the
  start is 0; "increased/decreased" only if p < 0.05; caveat when range < 30 years.

## Data handling

`backend/app/services/quality.py`: explicit °C / mm units, physical bounds → NaN and
counted, duplicate dates dropped, reindexed to a continuous daily calendar, trailing nulls
(ERA5 publication lag) trimmed, year completeness check. Every stored doc carries `source`,
`units`, `quality` and `fetched_at`.

## Security and performance

- Every query param is a typed Pydantic field; unknown params are rejected (`extra=forbid`).
- Mongo queries are built only from validated scalars (no `$` operator injection).
- Geocode query capped at 100 chars and URL-encoded by httpx.
- Per-IP limits: 30/min analysis, 60/min geocode. Outbound: semaphore of 4 concurrent
  Open-Meteo calls, 10 s timeout, up to 3 attempts on 429/5xx/timeouts with jittered backoff.
- CORS restricted to `ALLOWED_ORIGINS`; GET only.
- Pandas work is vectorized (run-length detection via `np.diff`) and runs off the event loop.

## Project structure

```
backend/
  app/
    main.py            FastAPI app factory, CORS, lifespan, DI
    config.py          settings from env
    errors.py          single error shape + handlers
    limiter.py         slowapi limiter
    schemas.py         request validation
    api/               hazards.py, geocode.py
    db/                mongo.py (client, indexes), repositories.py
    services/          open_meteo.py, quality.py, grid.py, analysis.py
    hazards/           base.py, registry.py, heatwave.py
    stats/             trend.py, insight.py
  tests/               unit + API tests (Mongo and Open-Meteo faked)
frontend/
  src/
    api/client.ts      typed fetch wrappers
    hooks/useHazard.ts TanStack Query hook + "waking server" state
    components/        RegionPicker, Charts, InsightCard, TopEvents
    App.tsx, types.ts
```

## Setup

Prerequisites: Python 3.11+, Node 20+, MongoDB (local or Atlas M0).

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # set MONGODB_URI
uvicorn app.main:app --reload # http://localhost:8000/docs

# frontend
cd frontend
cp .env.example .env          # VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev                   # http://localhost:5173

# tests
cd backend && pytest

# optional: pre-warm the cache for the preset cities (API must be running)
cd backend && python scripts/seed.py --api http://localhost:8000
```

Local MongoDB quickly: `docker run -d -p 27017:27017 mongo:7`.

## Deployment — TODO

- Backend (Render): start command
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`
  (proxy headers so rate limiting sees the real client IP).
- Frontend (Vercel): build `npm run build`, output `dist/`, set `VITE_API_BASE_URL`.
- Add the Vercel domain to `ALLOWED_ORIGINS`.

## Assumptions

1. Percentile baseline fixed at 1991–2020 for every analysis range.
2. Threshold is the annual 95th percentile of daily Tmax; calendar-day mode is a stretch goal.
3. ERA5 grid cells (~25 km) stand in for "the region"; points snap to the nearest cell.
4. Bounding boxes: daily values averaged across ≤ 25 sampled cells; box capped at 2°×2°.
5. Events are assigned to their start year; incomplete years are excluded.
6. Missing days end a heatwave run; no interpolation.
7. "Trend plots" from the API = plot-ready JSON series (`yearly[].rolling_mean`, `trend_line`).
8. Region focus: Andhra Pradesh and Telangana. Preset cities (Hyderabad, Visakhapatnam,
   Vijayawada, Warangal, Tirupati, …) and preset areas (Godavari delta, Rayalaseema, …) live
   in `backend/app/regions.py`. Areas are approximate rectangles, not official boundaries;
   whole states are not offered. Any other place still works via city search, lat/lon, or box.

## Known limitations

- ERA5 smooths peaks vs. stations and misses urban heat islands.
- A fixed annual threshold mostly detects summer heat.
- Bbox averaging underestimates local extremes.
- Rate limiter and geocode cache are in-process (fine for one instance; Redis for more).
- An event still running on Dec 31 of the last selected year is cut at the range end.

## What I would improve with more time — TODO

## AI tools used — TODO

| Tool | How it was used |
|---|---|
| Claude (Anthropic) | Analyzing the case study, drafting the plan; scaffolding backend/frontend code. **TODO:** note what you reviewed, rewrote, and verified by hand. |

---

*Weather data by [Open-Meteo.com](https://open-meteo.com/), licensed under CC BY 4.0.
ERA5 data from the Copernicus Climate Change Service.*
