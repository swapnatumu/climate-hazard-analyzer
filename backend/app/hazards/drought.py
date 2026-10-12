"""Drought, version 1: dry spells (consecutive dry days, the ETCCDI "CDD" idea).

A dry day has less than 1 mm of precipitation. The headline metric is the longest run of
dry days inside each calendar year. Annual rainfall is also compared with the fixed
baseline mean, so a year can be read as wetter or drier than normal.
"""

from typing import Any

import numpy as np
import pandas as pd

from app.hazards.base import Event, Threshold, run_lengths

DRY_DAY_MM = 1.0
MIN_SPELL_DAYS = 20  # shorter dry runs are ordinary weather, not listed as events
MIN_DAYS_FOR_ANNUAL_TOTAL = 347  # 95% of a year


class Drought:
    key = "drought"
    label = "Drought (dry spells)"
    variables = ["prcp"]
    primary_metric = "max_dry_spell"
    uses: tuple[str, ...] = ()
    rank_metric = "duration"
    caveats = [
        "Reanalysis precipitation is less reliable than temperature; read rainfall-based "
        "results as indicative.",
        "Dry-spell length is measured inside each calendar year, so a dry season that "
        "crosses New Year is split in two.",
    ]
    seasonal_label = ("Rainfall by month", "mm per month")

    def default_params(self) -> dict[str, Any]:
        return {"dry_day_mm": DRY_DAY_MM, "min_spell_days": MIN_SPELL_DAYS}

    def threshold(self, baseline: pd.DataFrame, params: dict[str, Any]) -> Threshold:
        prcp = baseline["prcp"].dropna()
        if prcp.empty:
            raise ValueError("Baseline period has no precipitation data")
        years = (int(prcp.index.year.min()), int(prcp.index.year.max()))
        g = prcp.groupby(prcp.index.year)
        annual = g.sum()[g.count() >= MIN_DAYS_FOR_ANNUAL_TOTAL]
        mean_annual = float(annual.mean()) if len(annual) else float("nan")
        return Threshold(
            value=DRY_DAY_MM, unit="mm/day", baseline=years, mode="fixed",
            description="a dry day has less than 1 mm of precipitation",
            reference={"mean_annual_precip": round(mean_annual, 1)},
        )

    def detect(self, df: pd.DataFrame, th: Threshold, params: dict[str, Any]) -> list[Event]:
        prcp = df["prcp"].to_numpy(dtype=float)
        # NaN < 1 is False, so a missing day always ends the current dry run.
        dry = prcp < th.value
        events: list[Event] = []
        for s, e in run_lengths(dry):
            duration = e - s + 1
            if duration < MIN_SPELL_DAYS:
                continue
            events.append(Event(start=df.index[s].date(), end=df.index[e].date(),
                                duration=duration,
                                metrics={"precip_total": float(prcp[s : e + 1].sum())}))
        return events

    def seasonal(self, df: pd.DataFrame, th: Threshold) -> pd.Series:
        return df["prcp"].fillna(0.0)

    def yearly_metrics(self, events: list[Event], years: list[int],
                       df: pd.DataFrame | None = None,
                       th: Threshold | None = None) -> pd.DataFrame:
        cols = ["max_dry_spell", "dry_days", "dry_spell_count", "total_precip",
                "precip_anomaly_pct"]
        out = pd.DataFrame(np.nan, index=pd.Index(years, name="year"), columns=cols)
        if df is None or th is None or df.empty:
            return out

        prcp = df["prcp"]
        dry = prcp < th.value
        by_year = prcp.index.year
        out["dry_days"] = dry.groupby(by_year).sum().reindex(years)
        out["total_precip"] = prcp.groupby(by_year).sum(min_count=1).reindex(years)
        # Longest dry run inside each calendar year (one slice per year, not per day).
        for y, mask in dry.groupby(by_year):
            if y in out.index:
                runs = run_lengths(mask.to_numpy())
                out.at[y, "max_dry_spell"] = max((e - s + 1 for s, e in runs), default=0)

        counts = pd.Series([e.year for e in events], dtype=int).value_counts()
        out["dry_spell_count"] = counts.reindex(years).fillna(0).to_numpy()

        normal = th.reference.get("mean_annual_precip", float("nan"))
        if normal and normal > 0:
            out["precip_anomaly_pct"] = (out["total_precip"] - normal) / normal * 100
        return out[cols].astype(float)
