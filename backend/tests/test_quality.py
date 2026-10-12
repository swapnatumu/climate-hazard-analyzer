import numpy as np
import pandas as pd

from app.services.quality import clean_daily, complete_years


def test_out_of_range_set_to_nan_and_counted():
    raw = pd.DataFrame({"date": ["2000-01-01", "2000-01-02"], "tmax": [75.0, 30.0]})
    df, rep = clean_daily(raw)
    assert np.isnan(df.loc["2000-01-01", "tmax"])
    assert rep.out_of_range == 1


def test_duplicates_dropped_and_gaps_reindexed():
    raw = pd.DataFrame({"date": ["2000-01-03", "2000-01-01", "2000-01-01"],
                        "tmax": [30.0, 31.0, 99.0]})
    df, rep = clean_daily(raw)
    assert rep.duplicates == 1
    assert list(df.index.strftime("%Y-%m-%d")) == ["2000-01-01", "2000-01-02", "2000-01-03"]
    assert np.isnan(df.loc["2000-01-02", "tmax"])


def test_trailing_nulls_trimmed():
    raw = pd.DataFrame({"date": ["2000-01-01", "2000-01-02", "2000-01-03"],
                        "tmax": [30.0, None, None]})
    df, _ = clean_daily(raw)
    assert len(df) == 1


def test_year_completeness():
    idx = pd.date_range("2000-01-01", "2001-12-31", freq="D")
    tmax = np.ones(len(idx))
    tmax[: 30] = np.nan  # 2000 loses 30 days -> below 95%
    df = pd.DataFrame({"tmax": tmax}, index=idx)
    assert complete_years(df, "tmax", [2000, 2001]) == {2000: False, 2001: True}
