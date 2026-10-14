# Climate Hazard Trend Analyzer

A web app that analyzes historical daily weather for a selected region and shows how
climate hazards have changed over time. Three hazards: heatwave (default), drought (dry
spells) and heavy rainfall.

> **Status:** heatwave, drought and heavy-rainfall analyses work end to end against live
> Open-Meteo (ERA5) data, with city search, presets, a Leaflet map (point and box), six
> charts per hazard, an insight card and CSV export. Not yet done: PDF export, SPI-based
> drought, calendar-day heatwave thresholds.

**Live:** [app](https://climate-hazard-analyzer-gold.vercel.app) ·
[API docs](https://climate-hazard-api-sh76.onrender.com/docs) · 
[demo video](https://drive.google.com/file/d/1hl5xkHOWrUfwhimphqEd9pgpMjHVQoMV/view?usp=drive_link)

The backend is on a free host that sleeps when idle, so the first request can take about a
minute.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript |
| Charts | Chart.js via `react-chartjs-2` |
| Map | `react-leaflet` with OpenStreetMap tiles (no API key) |
| Client cache | TanStack Query (1 h stale time) |
| Backend | FastAPI (Python 3.10+) |
| HTTP client | `httpx` + `tenacity` (timeouts, retries with backoff + jitter) |
| Analysis | `pandas`, `numpy`, `scipy`, `pymannkendall` |
| Rate limiting | `slowapi` (per IP) |
| Database | MongoDB (Atlas M0 or local) via PyMongo's native async client |
| Hosting | Vercel (frontend), Render (backend) |

> Deviation from the plan: the plan named `motor`. Motor is deprecated in favour of PyMongo's
> built-in async API (`AsyncMongoClient`), so the backend uses that instead. Same driver
> team, near-identical API.

## Data source

Daily maximum temperature, minimum temperature and precipitation from the
[Open-Meteo historical weather API](https://open-meteo.com/en/docs/historical-weather-api),
which serves the ERA5 reanalysis from the Copernicus Climate Change Service.

- Coverage: 1940 to the last complete year, worldwide, on a 0.25° grid (about 25 km).
- Why this one: no API key, one request returns decades of daily values for a cell, and
  reanalysis has no station gaps, so every place has the same record length. NOAA NCEI
  station data is closer to what a thermometer measured but has gaps and uneven coverage
  in India; the Copernicus CDS itself needs an account and queued file downloads.
- Cost of that choice: a grid cell is an area average, so peaks are lower than at a
  station, and precipitation is less reliable than temperature (see Known limitations).
- Geocoding for city search also comes from Open-Meteo.

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
| GET | `/api/regions` | Preset cities for every Indian state and union territory |
| GET | `/api/geocode?q=pune` | City search via Open-Meteo, cached in-process (24 h) |
| GET | `/api/hazards` | Available hazards and defaults |
| GET | `/api/hazards/{hazard}?lat=&lon=&start=&end=` | Analysis for a point |
| GET | `/api/hazards/{hazard}?bbox=minLon,minLat,maxLon,maxLat&start=&end=` | Analysis for a box (≤ 2°×2°, ≤ 25 sampled cells) |
| GET | `/api/hazards/{hazard}/export.csv?...` | Yearly metrics as CSV |

Optional params: `percentile` (90–99, default 95; heatwave and rainfall), `min_days` (2–7,
default 3; heatwave), `threshold_mode` (`annual` only for now). A hazard ignores the
parameters it does not use, and they are left out of its cache key.

Errors always look like `{"error": {"code": "VALIDATION_ERROR", "message": "..."}}`.
Status codes: 422 validation, 404 unknown hazard, 429 rate-limited (with `Retry-After`), 502/504 upstream
failure/timeout, 503 (`UPSTREAM_RATE_LIMITED`, with `Retry-After`) when Open-Meteo's free
quota is temporarily used up.

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

## Hazard logic: drought (dry spells)

Version 1 of the plan's drought hazard: consecutive dry days. Code: `backend/app/hazards/drought.py`.

- A dry day has less than 1 mm of precipitation (fixed, not a percentile).
- Headline metric `max_dry_spell`: the longest run of dry days **inside each calendar year**.
  A dry season that crosses New Year is split in two, so every year is measured the same
  way and the last year of the range is not cut short.
- Per year also: `dry_days`, `total_precip`, `precip_anomaly_pct` (annual rainfall against
  the 1991–2020 mean) and `dry_spell_count`.
- Events are dry spells of 20+ days, detected across year boundaries and assigned to their
  start year. A missing day ends a spell.

## Hazard logic: heavy rainfall

ETCCDI-style R95p. Code: `backend/app/hazards/rainfall.py`.

- Threshold = 95th percentile of baseline **wet days** (≥ 1 mm). Using all days would put
  the threshold near zero anywhere with a long dry season.
- Headline metric `heavy_days`: days per year above the threshold.
- Per year also: `heavy_precip` and `other_precip` (mm on heavy days and on the rest),
  `heavy_share_pct`, `rx1day` and `rx5day` (wettest day and wettest 5-day total).
- Events are runs of consecutive heavy days, so a multi-day storm is one event.

## Charts

Each hazard has its own set, defined in `frontend/src/hazardViews.ts` and drawn by
`components/Charts.tsx`: bars with a 5-year rolling mean and Sen's trend line, filled
lines, plain lines against the threshold, a diverging bar (rainfall above/below the
baseline), a stacked bar (heavy rain as part of the annual total), a monthly profile
comparing the first and second half of the range, and a bubble chart of every event by
year and time of year.

## Interface

- Light and dark themes with a header toggle; the first visit follows the OS setting and
  the choice is remembered. Chart colours are re-stepped per theme (`frontend/src/theme.tsx`).
- One accent colour per hazard, applied to the whole page from the hazard picker.
- A wide map that is always visible: click a point, draw a box, or pick a preset and the
  map flies to it.
- Results open with four headline tiles (threshold, events, first vs last decade, trend).
  The decade change is greyed out when the trend is not statistically significant.
- Motion is limited to entrances, count-ups, loading skeletons and hover feedback, and is
  switched off under `prefers-reduced-motion`.

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
`units`, `quality` (missing, out-of-range and duplicate counts for that cell-year) and
`fetched_at`.

Each analysis response has a `data_quality` block: days missing in the requested range for
the hazard's variable, the years excluded as incomplete, and how many out-of-range values
and duplicate dates were removed from the data it loaded. The insight card and the CSV
export show the same numbers.

## Security and performance

- Every query param is a typed Pydantic field; unknown params are rejected (`extra=forbid`).
- Mongo queries are built only from validated scalars (no `$` operator injection).
- Geocode query capped at 100 chars and URL-encoded by httpx.
- Per-IP limits: 30/min analysis, 60/min geocode. The client address is never taken from
  `X-Forwarded-For`, which a client can forge to get a fresh quota per request. It comes
  from the header named in `CLIENT_IP_HEADER` (`CF-Connecting-IP` on Render, set by
  Cloudflare), or from the socket when that is unset. Outbound: semaphore of 4 concurrent
  Open-Meteo calls, 10 s timeout, up to 3 attempts on 5xx/timeouts with jittered backoff.
  An upstream 429 is not retried (its quota windows are a minute or longer): the API fails
  fast with a 503 and `Retry-After`. Cells fetched before the limit stay cached, so a retry
  continues where it stopped.
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
    hazards/           base.py, registry.py, heatwave.py, drought.py, rainfall.py
    stats/             trend.py, insight.py
  tests/               unit + API tests (Mongo and Open-Meteo faked)
frontend/
  src/
    api/client.ts      typed fetch wrappers
    hooks/useHazard.ts TanStack Query hook + "waking server" state
    components/        HazardPicker, RegionPicker, MapSelector, Welcome, StatTiles,
                       Charts, InsightCard, TopEvents, Icons
    theme.tsx          light/dark theme and chart palettes
    hazardViews.ts     charts and table columns per hazard
    App.tsx, types.ts
render.yaml            Render blueprint for the backend
```

## Setup

Prerequisites: Python 3.10+, Node 20+, MongoDB (local or Atlas M0).

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

## Deployment

1. **Database (MongoDB Atlas M0):** create a database user with read/write on the `climate`
   database only. Render's free tier has no static outbound IP, so network access allows
   `0.0.0.0/0`; the credentials are the protection.
2. **Backend (Render):** New → Blueprint → this repo. `render.yaml` sets the root directory,
   build and start commands, health check and Python version. Set `MONGODB_URI` (Atlas
   connection string) and `ALLOWED_ORIGINS` in the dashboard. `CLIENT_IP_HEADER` comes from
   `render.yaml`.
3. **Frontend (Vercel):** import the repo with root directory `frontend` (Vite is detected:
   build `npm run build`, output `dist/`). Set `VITE_API_BASE_URL` to the Render URL.
4. Put the Vercel URL in Render's `ALLOWED_ORIGINS` (no trailing slash) and redeploy.
5. Pre-warm the demo cities: `python scripts/seed.py --api https://<render-url>`.

## Assumptions

1. Percentile baseline fixed at 1991–2020 for every analysis range.
2. Threshold is the annual 95th percentile of daily Tmax; calendar-day mode is a stretch goal.
3. ERA5 grid cells (~25 km) stand in for "the region"; points snap to the nearest cell.
4. Bounding boxes: daily values averaged across ≤ 25 sampled cells; box capped at 2°×2°.
5. Events are assigned to their start year; incomplete years are excluded.
6. Missing days end a heatwave run; no interpolation.
7. "Trend plots" from the API = plot-ready JSON series (`yearly[].rolling_mean`, `trend_line`).
8. Regions: the brief asks for "city, state, or a custom lat-lon box". Presets are chosen
   by state and then city: one to four main cities for each of the 28 states and 8 union
   territories (`backend/app/regions.py`). A whole state is not analysed as one region,
   because averaging daily weather over an area that size (Rajasthan spans desert and
   hills) hides the extremes this app is looking for; the 2°×2° box cap exists for the same
   reason. Any other place works via city search, lat/lon, a typed box, or the map.

## Known limitations

- ERA5 smooths peaks vs. stations and misses urban heat islands.
- A fixed annual threshold mostly detects summer heat.
- Reanalysis precipitation is less reliable than temperature and smooths local downpours,
  so drought and heavy-rainfall results carry more uncertainty than heatwave results.
- Calendar-year dry spells split a dry season that crosses New Year; in monsoon climates
  the yearly figure is mostly the January-to-monsoon stretch.
- Bbox averaging underestimates local extremes.
- Rate limiter and geocode cache are in-process (fine for one instance; Redis for more).
- An event still running on Dec 31 of the last selected year is cut at the range end.
- Open-Meteo's free tier weights each call by the days requested, so decades of daily data
  for one cell uses a large share of the per-minute quota. A box over many uncached cells
  can need a few retries a minute apart (progress is cached). The first analysis of a
  preset city that nobody has opened yet makes one upstream fetch.
- Free hosting: the Render instance sleeps after 15 minutes idle (about a minute to wake)
  and Atlas M0 stores 512 MB, enough for a few hundred cells.

## What I would improve with more time

- Validate ERA5 against NOAA GHCN-Daily station data for selected cities and show the bias.
- SPI-3 / SPEI for drought (dry spells say nothing about how much rain a wet season
  brought), and a calendar-day heatwave threshold so unusually warm winter spells count too.
- For boxes, detect events per grid cell and show the share of the area affected, instead
  of averaging first.
- A heatwave definition that also uses Tmin, since hot nights matter for health.
- Fetch data in a background job with progress polling, so a cold box does not depend on
  one request staying inside the upstream quota.
- Redis for rate limiting and request coalescing across multiple instances.
- Confidence intervals on Sen's slope and a pre-whitened Mann-Kendall test for
  autocorrelation.
- PDF export, end-to-end tests (Playwright), CI, and keyboard-accessible map controls.

## AI tools used

| Tool | How it was used |
|---|---|
| Claude (Anthropic), chat | Analyzing the case study, comparing data sources, drafting the hazard definitions, architecture and implementation plan. |
| Claude Code | Scaffolding the backend and frontend from that plan, the Leaflet map selector, the drought and heavy-rainfall hazards and their charts, the upstream rate-limit handling, tests, `render.yaml`, and this README. |

---

*Weather data by [Open-Meteo.com](https://open-meteo.com/), licensed under CC BY 4.0.
ERA5 data from the Copernicus Climate Change Service.*
