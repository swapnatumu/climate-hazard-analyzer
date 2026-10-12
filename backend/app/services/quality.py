"""Validation and cleaning of raw daily weather before it is stored or analyzed."""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Physical plausibility bounds; values outside are set to NaN and counted.
BOUNDS = {
    "tmax": (-90.0, 60.0),
    "tmin": (-90.0, 60.0),
    "prcp": (0.0, 1000.0),
}
COMPLETE_YEAR_MIN_FRACTION = 0.95


@dataclass
class QualityReport:
    missing: int = 0
    out_of_range: int = 0
    duplicates: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"missing": self.missing, "out_of_range": self.out_of_range,
                "duplicates": self.duplicates}


def clean_daily(raw: pd.DataFrame) -> tuple[pd.DataFrame, QualityReport]:
    """Return a continuous, sorted, bounds-checked daily frame indexed by date.

    `raw` has a `date` column plus any of tmax/tmin/prcp.
    """
    report = QualityReport()
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"])
    before = len(df)
    df = df.drop_duplicates(subset="date", keep="first").sort_values("date")
    report.duplicates = before - len(df)

    # Trailing nulls are ERA5's publication lag, not real gaps: trim them.
    value_cols = [c for c in BOUNDS if c in df.columns]
    has_data = df[value_cols].notna().any(axis=1).to_numpy()
    if has_data.any():
        df = df.iloc[: int(np.flatnonzero(has_data)[-1]) + 1]

    df = df.set_index("date")
    full = pd.date_range(df.index.min(), df.index.max(), freq="D", name="date")
    df = df.reindex(full)
    # Gaps (null or absent dates) before bounds checks; out-of-range is counted separately.
    report.missing = int(df[value_cols].isna().any(axis=1).sum())

    for col in value_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
        lo, hi = BOUNDS[col]
        bad = (df[col] < lo) | (df[col] > hi)
        n_bad = int(bad.sum())
        if n_bad:
            log.warning("quality: %d %s values out of range [%s, %s] set to NaN", n_bad, col, lo, hi)
            df.loc[bad, col] = np.nan
        report.out_of_range += n_bad

    return df, report


def complete_years(df: pd.DataFrame, column: str, years: list[int]) -> dict[int, bool]:
    """A year is complete when at least 95% of its calendar days have a value."""
    counts = df[column].notna().groupby(df.index.year).sum()
    out = {}
    for y in years:
        days_in_year = 366 if pd.Timestamp(year=y, month=12, day=31).dayofyear == 366 else 365
        out[y] = bool(counts.get(y, 0) >= COMPLETE_YEAR_MIN_FRACTION * days_in_year)
    return out
