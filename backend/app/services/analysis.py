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
from app.services.quality import QualityReport, clean_daily, complete_years
from app.stats.insight import build_insight
from app.stats.trend import analyze_trend, rolling_mean

log = logging.getLogger(__name__)

SOURCE = "open-meteo/era5"
UNITS = {"tmax": "°C", "tmin": "°C", "prcp": "mm"}
TOP_EVENTS = 5
MAX_EVENTS = 400  # cap on the per-event list sent to the client
ROLLING_WINDOW = 5
REMOVED_KEYS = ("out_of_range", "duplicates")  # counted per cell-year at ingest


def hazard_params(hazard, q: AnalysisQuery) -> dict:
    """Hazard constants plus only the query parameters this hazard actually reads."""
    return {**hazard.default_params(), **{k: getattr(q, k) for k in hazard.uses}}


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

    async def load_cell(self, cell: Cell, years: list[int]) -> tuple[pd.DataFrame, dict[str, int]]:
        """Daily frame for one cell plus what cleaning removed from those years."""
        async with self._cell_locks[cell.key]:
            docs = await self.weather.get_years(cell, years)
            missing = sorted(set(years) - docs.keys())
            if missing:
                log.info("cache miss %s: fetching %d-%d", cell.key, missing[0], missing[-1])
                raw = await self.upstream.fetch_daily(
                    cell.lat, cell.lon, date(missing[0], 1, 1), date(missing[-1], 12, 31)
                )
                df, report = clean_daily(raw)
                new_docs = _year_docs(cell, df, report, missing)
                await self.weather.upsert_years(new_docs)
                docs.update({d["year"]: d for d in new_docs})
        used = [docs[y] for y in years if y in docs]
        removed = {k: sum(d.get("quality", {}).get(k, 0) for d in used) for k in REMOVED_KEYS}
        return _docs_to_frame(used), removed

    async def load_region(self, cells: list[Cell], years: list[int]) -> tuple[pd.DataFrame, dict[str, int]]:
        loaded = await asyncio.gather(*(self.load_cell(c, years) for c in cells))
        frames = [f for f, _ in loaded]
        removed = {k: sum(r[k] for _, r in loaded) for k in REMOVED_KEYS}
        if len(frames) == 1:
            return frames[0], removed
        # Bounding box: spatial mean across sampled cells (smooths local extremes).
        return pd.concat(frames).groupby(level=0).mean(), removed

    # ---------- analysis ----------

    def result_key(self, hazard: str, cells: list[Cell], q: AnalysisQuery) -> str:
        payload = json.dumps(
            {
                "cells": [c.key for c in cells],
                "hazard": hazard,
                "baseline": [self.settings.baseline_start, self.settings.baseline_end],
                "range": [q.start, q.end],
                "params": hazard_params(HAZARDS[hazard], q),
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
        df, removed = await self.load_region(cells, years)

        try:
            result = await asyncio.to_thread(self._compute, hazard_key, df, q, (b0, b1))
        except ValueError as e:
            raise InsufficientData(str(e)) from e
        # Counts cover every cell and year loaded (baseline and requested range).
        result["data_quality"].update({f"{k}_removed": n for k, n in removed.items()})
        result.update({"_id": key, "region": region, "cache": "miss"})
        await self.results.put(result)
        return result

    def _compute(self, hazard_key: str, df: pd.DataFrame, q: AnalysisQuery,
                 baseline: tuple[int, int]) -> dict:
        hazard = HAZARDS[hazard_key]
        params = hazard_params(hazard, q)
        range_years = list(range(q.start, q.end + 1))

        base_df = df.loc[f"{baseline[0]}-01-01":f"{baseline[1]}-12-31"]
        th = hazard.threshold(base_df, params)

        range_df = df.loc[f"{q.start}-01-01":f"{q.end}-12-31"]
        events = hazard.detect(range_df, th, params)
        complete = complete_years(range_df, hazard.variables[0], range_years)

        yearly = hazard.yearly_metrics(events, range_years, range_df, th)
        # Incomplete years are excluded from trends (a partial year biases counts down).
        incomplete = [y for y, ok in complete.items() if not ok]
        yearly.loc[incomplete] = np.nan

        expected_days = pd.date_range(f"{q.start}-01-01", f"{q.end}-12-31", freq="D")
        metric = hazard.primary_metric
        series = yearly[metric]
        caveats = [
            "ERA5 is a ~25 km grid-cell average; weather-station peaks may be higher.",
        ]
        caveats += hazard.caveats
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

        ranked = sorted(events, key=lambda e: e.metrics.get(hazard.rank_metric, e.duration),
                        reverse=True)
        shown = sorted(ranked[:MAX_EVENTS], key=lambda e: e.start)
        return {
            "hazard": hazard_key,
            "params": {**params, "baseline": list(baseline)},
            "range": [q.start, q.end],
            "threshold": {"value": th.value, "unit": th.unit, "mode": th.mode,
                          "baseline": list(th.baseline), "percentile": params.get("percentile"),
                          "description": th.description, "reference": th.reference},
            "primary_metric": metric,
            "yearly": yearly_rows,
            "top_events": [e.to_dict() for e in ranked[:TOP_EVENTS]],
            "events": [e.to_dict() for e in shown],
            "event_total": len(events),
            "seasonality": _seasonality(hazard, range_df, th, complete),
            "trend": trend.to_dict(),
            "insight": insight,
            "comparison": comparison,
            "caveats": caveats,
            "data_quality": {
                "variable": hazard.variables[0],
                "days": len(expected_days),
                "missing_days": int(range_df[hazard.variables[0]].reindex(expected_days).isna().sum()),
                "incomplete_years": incomplete,
            },
            "source": SOURCE,
            "algo_version": self.settings.algo_version,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }


class InsufficientData(Exception):
    """The data cannot support this analysis (e.g. no wet days in the baseline)."""


def _seasonality(hazard, df: pd.DataFrame, th, complete: dict[int, bool]) -> dict | None:
    """Mean monthly profile for the first and second half of the range (complete years only)."""
    years = [y for y, ok in complete.items() if ok]
    if len(years) < 2:
        return None
    s = hazard.seasonal(df, th)
    monthly = (s.groupby([s.index.year, s.index.month]).sum().unstack()
               .reindex(index=years, columns=range(1, 13)))
    half = len(years) // 2
    title, unit = hazard.seasonal_label
    return {
        "title": title,
        "unit": unit,
        "periods": [
            {"label": f"{part[0]}–{part[-1]}",
             "values": [_num(v) for v in monthly.loc[part].mean()]}
            for part in (years[:half], years[half:])
        ],
    }


def _num(v) -> float | None:
    if v is None:
        return None
    f = float(v)
    return None if np.isnan(f) else round(f, 3)


def _year_docs(cell: Cell, df: pd.DataFrame, report: QualityReport, years: list[int]) -> list[dict]:
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
            "quality": {"missing": missing,
                        "out_of_range": report.out_of_range_by_year.get(y, 0),
                        "duplicates": report.duplicates_by_year.get(y, 0)},
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
