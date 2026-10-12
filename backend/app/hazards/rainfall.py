"""Heavy rainfall: days wetter than the baseline percentile of wet days (ETCCDI "R95p").

The percentile is taken over baseline *wet* days (>= 1 mm) only. Using all days would put
the threshold near zero anywhere with a long dry season.
"""

from typing import Any

import numpy as np
import pandas as pd

from app.hazards.base import Event, Threshold, run_lengths

WET_DAY_MM = 1.0


class HeavyRainfall:
    key = "rainfall"
    label = "Heavy rainfall"
    variables = ["prcp"]
    primary_metric = "heavy_days"
    uses = ("percentile",)
    rank_metric = "total_precip"
    caveats = [
        "Reanalysis precipitation is less reliable than temperature and underestimates "
        "local downpours; read rainfall-based results as indicative.",
    ]
    seasonal_label = ("Heavy-rain days by month", "days per year")

    def default_params(self) -> dict[str, Any]:
        return {"percentile": 95, "wet_day_mm": WET_DAY_MM}

    def threshold(self, baseline: pd.DataFrame, params: dict[str, Any]) -> Threshold:
        prcp = baseline["prcp"].dropna()
        wet = prcp[prcp >= WET_DAY_MM]
        if wet.empty:
            raise ValueError("Baseline period has no wet days, so no heavy-rain threshold exists")
        years = (int(prcp.index.year.min()), int(prcp.index.year.max()))
        value = float(np.quantile(wet.to_numpy(), params["percentile"] / 100))
        return Threshold(
            value=round(value, 2), unit="mm/day", baseline=years, mode="wet_day_percentile",
            description=f"p{params['percentile']} of baseline wet days (≥ 1 mm)",
        )

    def detect(self, df: pd.DataFrame, th: Threshold, params: dict[str, Any]) -> list[Event]:
        prcp = df["prcp"].to_numpy(dtype=float)
        heavy = prcp > th.value  # NaN compares False
        events: list[Event] = []
        # Consecutive heavy days form one spell, so a multi-day storm is one event.
        for s, e in run_lengths(heavy):
            seg = prcp[s : e + 1]
            events.append(Event(start=df.index[s].date(), end=df.index[e].date(),
                                duration=e - s + 1,
                                metrics={"total_precip": float(seg.sum()),
                                         "peak_daily": float(seg.max())}))
        return events

    def seasonal(self, df: pd.DataFrame, th: Threshold) -> pd.Series:
        return (df["prcp"] > th.value).astype(float)

    def yearly_metrics(self, events: list[Event], years: list[int],
                       df: pd.DataFrame | None = None,
                       th: Threshold | None = None) -> pd.DataFrame:
        cols = ["heavy_days", "heavy_precip", "other_precip", "heavy_share_pct",
                "rx1day", "rx5day", "total_precip"]
        out = pd.DataFrame(np.nan, index=pd.Index(years, name="year"), columns=cols)
        if df is None or th is None or df.empty:
            return out

        prcp = df["prcp"]
        by_year = prcp.index.year
        heavy = prcp > th.value
        out["heavy_days"] = heavy.groupby(by_year).sum().reindex(years)
        out["heavy_precip"] = prcp.where(heavy, 0.0).groupby(by_year).sum().reindex(years)
        out["total_precip"] = prcp.groupby(by_year).sum(min_count=1).reindex(years)
        out["other_precip"] = out["total_precip"] - out["heavy_precip"]
        out["heavy_share_pct"] = (out["heavy_precip"] / out["total_precip"].where(out["total_precip"] > 0)) * 100
        out["rx1day"] = prcp.groupby(by_year).max().reindex(years)
        # Wettest 5-day total, assigned to the year the window ends in.
        out["rx5day"] = prcp.rolling(5, min_periods=5).sum().groupby(by_year).max().reindex(years)
        return out[cols].astype(float)
