from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Threshold:
    value: float
    unit: str
    baseline: tuple[int, int]
    mode: str = "annual"
    # Plain-language definition shown next to the value.
    description: str = ""
    # Other baseline statistics the hazard needs later (e.g. mean annual rainfall).
    reference: dict[str, float] = field(default_factory=dict)


def run_lengths(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return (start_idx, end_idx_inclusive) for every run of True values.

    Vectorized: finds rising/falling edges with np.diff instead of looping per day.
    """
    padded = np.concatenate(([False], mask.astype(bool), [False]))
    edges = np.flatnonzero(np.diff(padded.astype(np.int8)))
    starts, ends = edges[0::2], edges[1::2] - 1
    return list(zip(starts.tolist(), ends.tolist()))


@dataclass
class Event:
    start: date
    end: date
    duration: int
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def year(self) -> int:
        # An event belongs to the year it starts, so one crossing Dec 31 is counted once.
        return self.start.year

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration": self.duration,
            **{k: round(float(v), 2) for k, v in self.metrics.items()},
        }


class Hazard(Protocol):
    key: str
    label: str
    variables: list[str]
    # Name of the yearly metric used for the headline trend and insight.
    primary_metric: str
    # Query parameters this hazard reads; the rest are ignored and kept out of the cache key.
    uses: tuple[str, ...]
    # Event metric used to rank "top events" ("duration" ranks by length).
    rank_metric: str
    caveats: list[str]
    # (title, unit) of the monthly profile built from `seasonal()`.
    seasonal_label: tuple[str, str]

    def default_params(self) -> dict[str, Any]: ...

    def threshold(self, baseline: pd.DataFrame, params: dict[str, Any]) -> Threshold: ...

    def detect(self, df: pd.DataFrame, th: Threshold, params: dict[str, Any]) -> list[Event]: ...

    def yearly_metrics(self, events: list[Event], years: list[int],
                       df: pd.DataFrame | None = None,
                       th: Threshold | None = None) -> pd.DataFrame: ...

    def seasonal(self, df: pd.DataFrame, th: Threshold) -> pd.Series:
        """Daily values that are summed per month to show when in the year the hazard occurs."""
        ...
