from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

import pandas as pd


@dataclass(frozen=True)
class Threshold:
    value: float
    unit: str
    baseline: tuple[int, int]
    mode: str = "annual"


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

    def default_params(self) -> dict[str, Any]: ...

    def threshold(self, baseline: pd.DataFrame, params: dict[str, Any]) -> Threshold: ...

    def detect(self, df: pd.DataFrame, th: Threshold, params: dict[str, Any]) -> list[Event]: ...

    def yearly_metrics(self, events: list[Event], years: list[int]) -> pd.DataFrame: ...
