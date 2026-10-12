import numpy as np
import pandas as pd
import pytest

from app.hazards.base import Threshold
from app.hazards.drought import MIN_SPELL_DAYS, Drought

DR = Drought()
TH = Threshold(value=1.0, unit="mm/day", baseline=(1991, 2020),
               reference={"mean_annual_precip": 100.0})


def frame(values, start="2001-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="D", name="date")
    return pd.DataFrame({"prcp": np.array(values, dtype=float)}, index=idx)


def test_short_dry_run_is_not_an_event():
    assert DR.detect(frame([5] + [0] * (MIN_SPELL_DAYS - 1) + [5]), TH, {}) == []


def test_dry_spell_of_minimum_length_is_one_event():
    events = DR.detect(frame([5] + [0.4] * MIN_SPELL_DAYS + [5]), TH, {})
    assert len(events) == 1
    assert events[0].duration == MIN_SPELL_DAYS
    # Drizzle below 1 mm does not break the spell but is still counted as rain.
    assert events[0].metrics["precip_total"] == pytest.approx(0.4 * MIN_SPELL_DAYS)


def test_missing_day_breaks_a_dry_spell():
    values = [0.0] * 15 + [np.nan] + [0.0] * 15
    assert DR.detect(frame(values), TH, {}) == []


def test_yearly_longest_spell_is_measured_inside_the_calendar_year():
    # 40 dry days from 12 Dec 2001: 20 fall in 2001 and 20 in 2002.
    df = frame([10.0] * 345 + [0.0] * 40 + [10.0] * 345)
    yearly = DR.yearly_metrics(DR.detect(df, TH, {}), [2001, 2002], df, TH)
    assert yearly.loc[2001, "max_dry_spell"] == 20
    assert yearly.loc[2002, "max_dry_spell"] == 20
    assert yearly.loc[2001, "dry_days"] == 20
    # The spell itself is one event, counted in the year it starts.
    assert yearly.loc[2001, "dry_spell_count"] == 1
    assert yearly.loc[2002, "dry_spell_count"] == 0


def test_rainfall_anomaly_is_relative_to_the_baseline_mean():
    df = frame([1.0] * 365)  # 365 mm against a 100 mm normal
    yearly = DR.yearly_metrics([], [2001], df, TH)
    assert yearly.loc[2001, "total_precip"] == pytest.approx(365.0)
    assert yearly.loc[2001, "precip_anomaly_pct"] == pytest.approx(265.0)


def test_threshold_keeps_baseline_mean_annual_rainfall():
    th = DR.threshold(frame([2.0] * 730, start="1991-01-01"), {})
    assert th.value == 1.0
    assert th.reference["mean_annual_precip"] == pytest.approx(730.0)
