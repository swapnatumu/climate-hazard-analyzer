"""Turns a yearly series + trend result into one honest sentence.

Rules (see README, "Rules for the insight sentence"):
- Never compare two single years.
- Compare the first-decade mean with the last-decade mean; if the range is < 20 years,
  use Sen's fitted line at the start and end instead.
- If the starting value is 0, report an absolute change, not a percentage.
- Say "increased"/"decreased" only when Mann-Kendall p < 0.05.
"""

import pandas as pd

from app.stats.trend import TrendResult

# metric -> (noun, value unit, slope unit)
METRIC_PHRASES = {
    "event_count": ("Heatwave events", "per year", "events"),
    "heatwave_days": ("Heatwave days", "per year", "days"),
    "excess_heat": ("Excess heat", "°C·days per year", "°C·days"),
}


def _fmt(v: float) -> str:
    return f"{v:.1f}"


def build_insight(
    series: pd.Series, trend: TrendResult, metric: str
) -> tuple[str, dict, list[str]]:
    s = series.dropna()
    years = s.index.tolist()
    first, last = years[0], years[-1]
    span = last - first + 1
    caveats: list[str] = []
    noun, unit, slope_unit = METRIC_PHRASES.get(metric, (metric, "", ""))

    if span >= 20:
        a = float(s.loc[first : first + 9].mean())
        b = float(s.loc[last - 9 : last].mean())
        a_label, b_label = f"{first}–{first + 9}", f"{last - 9}–{last}"
        basis = "decade_means"
    else:
        fitted = trend.fitted(years)
        a, b = fitted[0], fitted[-1]
        a_label, b_label = str(first), str(last)
        basis = "trend_line"

    if span < 30:
        caveats.append(
            f"The selected range is {span} years; climate trends are usually judged over 30+ years."
        )

    p_txt = "p < 0.001" if trend.p_value < 0.001 else f"p = {trend.p_value:.3f}"
    sig = (
        f"Mann-Kendall {p_txt}; "
        f"Sen's slope {trend.slope_per_decade:+.2f} {slope_unit} per decade"
    )

    if not trend.significant:
        sentence = (
            f"{noun} went from {_fmt(a)} {unit} ({a_label}) to {_fmt(b)} {unit} ({b_label}), "
            f"but there is no statistically significant trend ({sig})."
        )
    else:
        verb = "increased" if trend.slope_per_decade > 0 else "decreased"
        if a == 0:
            change = f"from {_fmt(a)} to {_fmt(b)} {unit} ({a_label} vs {b_label})"
        else:
            pct = (b - a) / a * 100
            change = (
                f"from {_fmt(a)} {unit} ({a_label}) to {_fmt(b)} {unit} ({b_label}), "
                f"a {abs(pct):.0f}% {'rise' if pct >= 0 else 'fall'}"
            )
        sentence = f"{noun} {verb} {change}. The trend is statistically significant ({sig})."

    comparison = {"basis": basis, "start_label": a_label, "start_value": round(a, 3),
                  "end_label": b_label, "end_value": round(b, 3)}
    return sentence, comparison, caveats
