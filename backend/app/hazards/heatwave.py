"""Heatwave: N+ consecutive days with Tmax above the baseline percentile.

The threshold is computed once from the fixed baseline period (1991-2020 by default),
so changing the analysis range never changes what counts as a heatwave.
"""

from typing import Any

import numpy as np
import pandas as pd

from app.hazards.base import Event, Threshold


def run_lengths(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return (start_idx, end_idx_inclusive) for every run of True values.

    Vectorized: finds rising/falling edges with np.diff instead of looping per day.
    """
    padded = np.concatenate(([False], mask.astype(bool), [False]))
    edges = np.flatnonzero(np.diff(padded.astype(np.int8)))
    starts, ends = edges[0::2], edges[1::2] - 1
    return list(zip(starts.tolist(), ends.tolist()))


class Heatwave:
    key = "heatwave"
    label = "Heatwave"
    variables = ["tmax"]
    primary_metric = "event_count"

    def default_params(self) -> dict[str, Any]:
        return {"percentile": 95, "min_days": 3, "threshold_mode": "annual"}

    def threshold(self, baseline: pd.DataFrame, params: dict[str, Any]) -> Threshold:
        years = (int(baseline.index.year.min()), int(baseline.index.year.max()))
        tmax = baseline["tmax"].dropna()
        if tmax.empty:
            raise ValueError("Baseline period has no Tmax data")
        value = float(np.quantile(tmax.to_numpy(), params["percentile"] / 100))
        return Threshold(value=round(value, 2), unit="°C", baseline=years, mode="annual")

    def detect(self, df: pd.DataFrame, th: Threshold, params: dict[str, Any]) -> list[Event]:
        tmax = df["tmax"].to_numpy(dtype=float)
        # NaN > thr is False, so a missing day always ends the current run.
        hot = tmax > th.value
        events: list[Event] = []
        for s, e in run_lengths(hot):
            duration = e - s + 1
            if duration < params["min_days"]:
                continue
            seg = tmax[s : e + 1]
            exceed = seg - th.value
            events.append(
                Event(
                    start=df.index[s].date(),
                    end=df.index[e].date(),
                    duration=duration,
                    metrics={
                        "peak_tmax": float(seg.max()),
                        "mean_exceedance": float(exceed.mean()),
                        "excess_heat": float(exceed.sum()),
                    },
                )
            )
        return events

    def yearly_metrics(self, events: list[Event], years: list[int]) -> pd.DataFrame:
        cols = [
            "event_count",
            "heatwave_days",
            "mean_duration",
            "max_duration",
            "mean_intensity",
            "peak_tmax",
            "excess_heat",
        ]
        if not events:
            out = pd.DataFrame(0.0, index=pd.Index(years, name="year"), columns=cols)
            out[["mean_duration", "mean_intensity", "peak_tmax"]] = np.nan
            return out

        ev = pd.DataFrame(
            {
                "year": [e.year for e in events],
                "duration": [e.duration for e in events],
                "mean_exceedance": [e.metrics["mean_exceedance"] for e in events],
                "peak_tmax": [e.metrics["peak_tmax"] for e in events],
                "excess_heat": [e.metrics["excess_heat"] for e in events],
            }
        )
        g = ev.groupby("year")
        out = pd.DataFrame(
            {
                "event_count": g.size(),
                "heatwave_days": g["duration"].sum(),
                "mean_duration": g["duration"].mean(),
                "max_duration": g["duration"].max(),
                "mean_intensity": g["mean_exceedance"].mean(),
                "peak_tmax": g["peak_tmax"].max(),
                "excess_heat": g["excess_heat"].sum(),
            }
        ).reindex(years)
        # Years with no events: counts are 0, per-event averages stay NaN (undefined).
        out[["event_count", "heatwave_days", "max_duration", "excess_heat"]] = out[
            ["event_count", "heatwave_days", "max_duration", "excess_heat"]
        ].fillna(0)
        out.index.name = "year"
        return out[cols].astype(float)
