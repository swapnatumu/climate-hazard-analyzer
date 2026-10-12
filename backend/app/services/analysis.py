"""Orchestration: analysis cache -> raw daily cache -> Open-Meteo fetch -> compute -> store."""

import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from app.config import Settings
from app.db.repositories import ResultRepo, WeatherRepo
from app.hazards.registry import HAZARDS
from app.schemas import AnalysisQuery
from app.services.grid import Cell, bbox_cells, snap_point
from app.services.open_meteo import OpenMeteoClient
from app.services.quality import clean_daily, complete_years
from app.stats.insight import build_insight
from app.stats.trend import analyze_trend, rolling_mean

log = logging.getLogger(__name__)

SOURCE = "open-meteo/era5"
UNITS = {"tmax": "°C", "tmin": "°C", "prcp": "mm"}
TOP_EVENTS = 5
ROLLING_WINDOW = 5


class AnalysisService:
    def __init__(
        self,
        settings: Settings,
        weather: WeatherRepo,
        results: ResultRepo,
        upstream: OpenMeteoClient,
    ):
        self.settings = settings
        self.weather = weather
        self.results = results
        self.upstream = upstream
        # Request coalescing: concurrent requests for the same cell share one fetch.
        self._cell_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    # ---------- raw data ----------

    async def load_cell(self, cell: Cell, years: list[int]) -> pd.DataFrame:
        async with self._cell_locks[cell.key]:
            docs = await self.weather.get_years(cell, years)
            missing = sorted(set(years) - docs.keys())
            if missing:
                log.info("cache miss %s: fetching %d-%d", cell.key, missing[0], missing[-1])
                raw = await self.upstream.fetch_daily(
                    cell.lat, cell.lon, date(missing[0], 1, 1), date(missing[-1], 12, 31)
                )
                df, _ = clean_daily(raw)
                new_docs = _year_docs(cell, df, missing)
                await self.weather.upsert_years(new_docs)
                docs.update({d["year"]: d for d in new_docs})
        return _docs_to_frame([docs[y] for y in years if y in docs])

    async def load_region(self, cells: list[Cell], years: list[int]) -> pd.DataFrame:
        frames = await asyncio.gather(*(self.load_cell(c, years) for c in cells))
        if len(frames) == 1:
            return frames[0]
        # Bounding box: spatial mean across sampled cells (smooths local extremes).
        return pd.concat(frames).groupby(level=0).mean()

    # ---------- analysis ----------

    def result_key(self, hazard: str, cells: list[Cell], q: AnalysisQuery) -> str:
        payload = json.dumps(
            {
                "cells": [c.key for c in cells],
                "hazard": hazard,
                "baseline": [self.settings.baseline_start, self.settings.baseline_end],
                "range": [q.start, q.end],
                "params": {"percentile": q.percentile, "min_days": q.min_days,
                           "threshold_mode": q.threshold_mode},
                "algo_version": self.settings.algo_version,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    async def analyze(self, hazard_key: str, q: AnalysisQuery) -> dict:
        hazard = HAZARDS[hazard_key]
        if q.bbox_tuple:
            cells = bbox_cells(*q.bbox_tuple)
            region = {"type": "bbox", "bbox": list(q.bbox_tuple), "cells": len(cells)}
        else:
            cell = snap_point(q.lat, q.lon)  # type: ignore[arg-type]
            cells = [cell]
            region = {"type": "point", "cell": cell.to_dict(),
                      "requested": {"lat": q.lat, "lon": q.lon}}

        key = self.result_key(hazard_key, cells, q)
        cached = await self.results.get(key)
        if cached:
            cached["cache"] = "hit"
            return cached

        b0, b1 = self.settings.baseline_start, self.settings.baseline_end
        years = sorted(set(range(b0, b1 + 1)) | set(range(q.start, q.end + 1)))
        df = await self.load_region(cells, years)

        result = await asyncio.to_thread(self._compute, hazard_key, df, q, (b0, b1))
        result.update({"_id": key, "region": region, "cache": "miss"})
        await self.results.put(result)
        return result

    def _compute(self, hazard_key: str, df: pd.DataFrame, q: AnalysisQuery,
                 baseline: tuple[int, int]) -> dict:
        hazard = HAZARDS[hazard_key]
        params = {"percentile": q.percentile, "min_days": q.min_days,
                  "threshold_mode": q.threshold_mode}
        range_years = list(range(q.start, q.end + 1))

        base_df = df.loc[f"{baseline[0]}-01-01":f"{baseline[1]}-12-31"]
        th = hazard.threshold(base_df, params)

        range_df = df.loc[f"{q.start}-01-01":f"{q.end}-12-31"]
        events = hazard.detect(range_df, th, params)
        complete = complete_years(range_df, hazard.variables[0], range_years)

        yearly = hazard.yearly_metrics(events, range_years)
        # Incomplete years are excluded from trends (a partial year biases counts down).
        incomplete = [y for y, ok in complete.items() if not ok]
        yearly.loc[incomplete] = np.nan

        metric = hazard.primary_metric
        series = yearly[metric]
        caveats = [
            "ERA5 is a ~25 km grid-cell average; weather-station peaks may be higher.",
        ]
        if incomplete:
            caveats.append(f"Excluded {len(incomplete)} incomplete year(s): {incomplete}.")

        trend = analyze_trend(series)
        insight, comparison, insight_caveats = build_insight(series, trend, metric)
        caveats += insight_caveats

        trend_years = series.dropna().index.tolist()
        fitted = dict(zip(trend_years, trend.fitted(trend_years)))
        roll = rolling_mean(series, ROLLING_WINDOW)

        yearly_rows = []
        for y in range_years:
            row = {"year": y, "complete": complete[y]}
            row.update({c: _num(yearly.at[y, c]) for c in yearly.columns})
            row["rolling_mean"] = _num(roll.get(y))
            row["trend_line"] = _num(fitted.get(y))
            yearly_rows.append(row)

        top = sorted(events, key=lambda e: e.metrics["excess_heat"], reverse=True)[:TOP_EVENTS]
        return {
            "hazard": hazard_key,
            "params": {**params, "baseline": list(baseline)},
            "range": [q.start, q.end],
            "threshold": {"value": th.value, "unit": th.unit, "mode": th.mode,
                          "baseline": list(th.baseline), "percentile": q.percentile},
            "primary_metric": metric,
            "yearly": yearly_rows,
            "top_events": [e.to_dict() for e in top],
            "event_total": len(events),
            "trend": trend.to_dict(),
            "insight": insight,
            "comparison": comparison,
            "caveats": caveats,
            "source": SOURCE,
            "algo_version": self.settings.algo_version,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }


def _num(v) -> float | None:
    if v is None:
        return None
    f = float(v)
    return None if np.isnan(f) else round(f, 3)


def _year_docs(cell: Cell, df: pd.DataFrame, years: list[int]) -> list[dict]:
    now = datetime.now(timezone.utc)
    docs = []
    for y in years:
        idx = pd.date_range(f"{y}-01-01", f"{y}-12-31", freq="D")
        part = df.reindex(idx)
        arrays = {c: [None if pd.isna(v) else round(float(v), 2) for v in part[c]]
                  for c in UNITS if c in part.columns}
        missing = sum(v is None for v in arrays.get("tmax", []))
        docs.append({
            "_id": f"{cell.key}_{y}",
            "cell": cell.to_dict(),
            "year": y,
            "source": SOURCE,
            "units": UNITS,
            "dates_start": f"{y}-01-01",
            **arrays,
            "quality": {"missing": missing},
            "fetched_at": now,
        })
    return docs


def _docs_to_frame(docs: list[dict]) -> pd.DataFrame:
    frames = []
    for d in docs:
        n = len(d["tmax"])
        idx = pd.date_range(d["dates_start"], periods=n, freq="D", name="date")
        frames.append(pd.DataFrame({c: d.get(c, [None] * n) for c in UNITS}, index=idx,
                                   dtype=float))
    if not frames:
        return pd.DataFrame(columns=list(UNITS), index=pd.DatetimeIndex([], name="date"))
    return pd.concat(frames).sort_index()
