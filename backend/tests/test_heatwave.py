import numpy as np
import pandas as pd
import pytest

from app.hazards.base import Threshold
from app.hazards.heatwave import Heatwave

HW = Heatwave()
PARAMS = {"percentile": 95, "min_days": 3, "threshold_mode": "annual"}
TH = Threshold(value=40.0, unit="°C", baseline=(1991, 2020))


def frame(values, start="2000-06-01"):
    idx = pd.date_range(start, periods=len(values), freq="D", name="date")
    return pd.DataFrame({"tmax": np.array(values, dtype=float)}, index=idx)


def test_two_hot_days_is_not_an_event():
    assert HW.detect(frame([30, 41, 42, 30]), TH, PARAMS) == []


def test_three_hot_days_is_one_event():
    events = HW.detect(frame([30, 41, 42, 43, 30]), TH, PARAMS)
    assert len(events) == 1
    e = events[0]
    assert e.duration == 3
    assert e.metrics["peak_tmax"] == 43
    assert e.metrics["excess_heat"] == pytest.approx(6.0)
    assert e.metrics["mean_exceedance"] == pytest.approx(2.0)


def test_nan_breaks_a_run():
    assert HW.detect(frame([41, 42, np.nan, 41, 42]), TH, PARAMS) == []


def test_event_across_new_year_counts_once_in_start_year():
    events = HW.detect(frame([41, 42, 43, 44], start="2000-12-30"), TH, PARAMS)
    assert len(events) == 1
    yearly = HW.yearly_metrics(events, [2000, 2001])
    assert yearly.loc[2000, "event_count"] == 1
    assert yearly.loc[2001, "event_count"] == 0


def test_threshold_depends_only_on_baseline():
    rng = np.random.default_rng(0)
    idx = pd.date_range("1980-01-01", "2023-12-31", freq="D")
    df = pd.DataFrame({"tmax": rng.normal(30, 5, len(idx))}, index=idx)
    base = df.loc["1991":"2020"]
    th1 = HW.threshold(base, PARAMS)
    # Same baseline slice regardless of the analysis range the user picks.
    th2 = HW.threshold(df.loc["1950":"2023"].loc["1991":"2020"], PARAMS)
    assert th1.value == th2.value
    assert th1.baseline == (1991, 2020)


def test_years_without_events_have_zero_counts():
    yearly = HW.yearly_metrics([], [2000, 2001])
    assert (yearly["event_count"] == 0).all()
    assert yearly["mean_duration"].isna().all()
