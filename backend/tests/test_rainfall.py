import numpy as np
import pandas as pd
import pytest

from app.hazards.base import Threshold
from app.hazards.rainfall import HeavyRainfall

HR = HeavyRainfall()
PARAMS = {"percentile": 95}
TH = Threshold(value=50.0, unit="mm/day", baseline=(1991, 2020))


def frame(values, start="2001-06-01"):
    idx = pd.date_range(start, periods=len(values), freq="D", name="date")
    return pd.DataFrame({"prcp": np.array(values, dtype=float)}, index=idx)


def test_threshold_uses_wet_days_only():
    # 900 dry days must not drag the percentile towards zero.
    values = [0.0] * 900 + list(range(1, 101))
    th = HR.threshold(frame(values, start="1991-01-01"), PARAMS)
    assert th.value == pytest.approx(np.quantile(np.arange(1, 101), 0.95), abs=0.01)


def test_no_wet_days_in_baseline_is_an_error():
    with pytest.raises(ValueError):
        HR.threshold(frame([0.0] * 400, start="1991-01-01"), PARAMS)


def test_consecutive_heavy_days_are_one_spell():
    events = HR.detect(frame([0, 60, 80, 10, 55, 0]), TH, PARAMS)
    assert [e.duration for e in events] == [2, 1]
    assert events[0].metrics["total_precip"] == pytest.approx(140.0)
    assert events[0].metrics["peak_daily"] == 80


def test_a_day_exactly_at_the_threshold_is_not_heavy():
    assert HR.detect(frame([50.0, 50.0]), TH, PARAMS) == []


def test_yearly_metrics():
    df = frame([0, 60, 80, 10, 55, 0, 5])
    y = HR.yearly_metrics(HR.detect(df, TH, PARAMS), [2001], df, TH).loc[2001]
    assert y["heavy_days"] == 3
    assert y["heavy_precip"] == pytest.approx(195.0)
    assert y["total_precip"] == pytest.approx(210.0)
    assert y["other_precip"] == pytest.approx(15.0)
    assert y["heavy_share_pct"] == pytest.approx(195 / 210 * 100)
    assert y["rx1day"] == 80
    assert y["rx5day"] == pytest.approx(205.0)  # 60 + 80 + 10 + 55 + 0


def test_missing_day_is_never_heavy():
    assert HR.detect(frame([np.nan, np.nan]), TH, PARAMS) == []
