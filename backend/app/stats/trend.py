"""Trend statistics for a yearly series: rolling mean, Theil-Sen, Mann-Kendall, OLS."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats

ALPHA = 0.05


@dataclass
class TrendResult:
    method: str
    n_years: int
    sen_slope_per_year: float
    sen_intercept: float
    slope_per_decade: float
    p_value: float
    significant: bool
    direction: str  # "increasing" | "decreasing" | "no trend"
    ols_slope_per_decade: float
    ols_intercept: float
    ols_r2: float

    def fitted(self, years: list[int]) -> list[float]:
        """Sen's line evaluated at each year (x is years since the first year)."""
        x0 = years[0]
        return [self.sen_intercept + self.sen_slope_per_year * (y - x0) for y in years]

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


def rolling_mean(series: pd.Series, window: int = 5) -> pd.Series:
    """Centred rolling mean for display only; edges are left empty."""
    return series.rolling(window=window, center=True, min_periods=window).mean()


def analyze_trend(series: pd.Series) -> TrendResult:
    """Theil-Sen slope + Mann-Kendall significance, with OLS as a reference line.

    `series` is indexed by year. NaN years (incomplete data) are dropped first.
    """
    s = series.dropna()
    n = len(s)
    if n < 3:
        raise ValueError("Need at least 3 years for a trend")

    x = (s.index.to_numpy() - s.index[0]).astype(float)
    y = s.to_numpy(dtype=float)

    if np.allclose(y, y[0]):
        # Constant series (e.g. zero events every year): no trend by definition.
        slope, intercept, p = 0.0, float(y[0]), 1.0
    else:
        res = stats.theilslopes(y, x)
        slope, intercept = float(res.slope), float(res.intercept)
        p = float(mk.original_test(y).p)

    ols = stats.linregress(x, y) if not np.allclose(y, y[0]) else None
    significant = p < ALPHA
    if not significant or slope == 0:
        direction = "no trend"
    else:
        direction = "increasing" if slope > 0 else "decreasing"

    return TrendResult(
        method="mann-kendall+sen",
        n_years=n,
        sen_slope_per_year=slope,
        sen_intercept=intercept,
        slope_per_decade=slope * 10,
        p_value=p,
        significant=significant,
        direction=direction,
        ols_slope_per_decade=float(ols.slope * 10) if ols else 0.0,
        ols_intercept=float(ols.intercept) if ols else float(y[0]),
        ols_r2=float(ols.rvalue**2) if ols else 0.0,
    )
