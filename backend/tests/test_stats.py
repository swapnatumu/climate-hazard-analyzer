import numpy as np
import pandas as pd

from app.stats.insight import build_insight
from app.stats.trend import analyze_trend


def series(values, start=1990):
    return pd.Series(values, index=range(start, start + len(values)), dtype=float)


def test_flat_series_has_no_significant_trend():
    s = series([2.0] * 30)
    t = analyze_trend(s)
    assert not t.significant
    text, _, _ = build_insight(s, t, "event_count")
    assert "no statistically significant trend" in text


def test_linear_increase_is_significant():
    s = series(np.arange(30) * 0.1)
    t = analyze_trend(s)
    assert t.slope_per_decade > 0
    assert t.p_value < 0.05
    assert t.direction == "increasing"


def test_zero_first_decade_reports_absolute_change():
    s = series([0] * 10 + [1] * 10 + [3] * 10)
    t = analyze_trend(s)
    text, cmp, _ = build_insight(s, t, "event_count")
    assert cmp["start_value"] == 0
    assert "%" not in text
    assert "increased" in text


def test_short_range_adds_caveat_and_uses_trend_line():
    s = series(np.arange(15) * 0.2)
    t = analyze_trend(s)
    _, cmp, caveats = build_insight(s, t, "event_count")
    assert cmp["basis"] == "trend_line"
    assert any("30+ years" in c for c in caveats)
