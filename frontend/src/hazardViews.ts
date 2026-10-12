import type { SeriesColor } from "./theme";

// How each hazard is presented: which charts, in which form, and the table columns.
// Metric names match the yearly columns produced by backend/app/hazards/*.py.

interface Base { title: string; note?: string; wide?: boolean }
type Series = { metric: string; label: string };

export type ChartSpec =
  /** Bars per year with the 5-year rolling mean; `trend` adds Sen's slope line. */
  | (Base & { kind: "combo"; metric: string; yLabel: string; trend?: boolean })
  /** Filled line per year with the rolling mean. */
  | (Base & { kind: "area"; metric: string; yLabel: string; trend?: boolean })
  /** One or two plain lines; `threshold` adds the hazard threshold as a reference line. */
  | (Base & { kind: "lines"; series: Series[]; yLabel: string; threshold?: string })
  /** Bars above/below zero, coloured by sign. */
  | (Base & { kind: "diverging"; metric: string; yLabel: string; above: string; below: string })
  /** Two metrics stacked into one bar per year (parts of a whole). */
  | (Base & { kind: "stacked"; series: [Series, Series]; yLabel: string })
  /** Every event as a bubble: year across, time of year up, size by `size`. */
  | (Base & { kind: "events"; size: string; sizeLabel: string })
  /** Monthly profile, first half of the range against the second half. */
  | (Base & { kind: "seasonality" });

export interface HazardView {
  key: string;
  label: string;
  /** One-line definition shown on the hazard picker card. */
  blurb: string;
  question: string;
  /** Mark colour for this hazard's single-series charts. */
  color: SeriesColor;
  /** Unit of the headline metric, for the stat tiles. */
  unit: string;
  eventNoun: string;
  emptyText: string;
  usesPercentile: boolean;
  usesMinDays: boolean;
  charts: ChartSpec[];
  table: { title: string; columns: { key: string; label: string }[] };
}

export const HAZARD_VIEWS: Record<string, HazardView> = {
  heatwave: {
    key: "heatwave",
    label: "Heatwave",
    blurb: "3+ days in a row hotter than the 95th percentile",
    unit: "events per year",
    question: "How have heatwaves changed in a place over time?",
    color: "orange",
    eventNoun: "Heatwaves",
    emptyText: "No heatwaves detected in this range.",
    usesPercentile: true,
    usesMinDays: true,
    charts: [
      { kind: "combo", metric: "event_count", title: "Heatwave events per year", yLabel: "events",
        trend: true, wide: true },
      { kind: "area", metric: "heatwave_days", title: "Heatwave days per year", yLabel: "days" },
      { kind: "lines", series: [{ metric: "peak_tmax", label: "Hottest heatwave day" }],
        title: "Hottest heatwave day each year", yLabel: "°C", threshold: "Heatwave threshold",
        note: "Years without a heatwave have no point." },
      { kind: "combo", metric: "excess_heat", title: "Excess heat per year",
        yLabel: "°C·days above threshold" },
      { kind: "seasonality", title: "When in the year it gets this hot" },
      { kind: "events", title: "Every heatwave, by year and season", size: "duration",
        sizeLabel: "days", wide: true, note: "Bubble size = length in days." },
    ],
    table: {
      title: "Top heatwaves by excess heat",
      columns: [
        { key: "start", label: "Start" }, { key: "end", label: "End" }, { key: "duration", label: "Days" },
        { key: "peak_tmax", label: "Peak Tmax (°C)" }, { key: "mean_exceedance", label: "Mean exceedance (°C)" },
        { key: "excess_heat", label: "Excess heat (°C·days)" },
      ],
    },
  },

  drought: {
    key: "drought",
    label: "Drought",
    blurb: "Long runs of days with under 1 mm of rain",
    unit: "days",
    question: "Are dry spells getting longer, and are years getting drier?",
    color: "yellow",
    eventNoun: "Dry spells of 20+ days",
    emptyText: "No dry spells of 20 days or more in this range.",
    usesPercentile: false,
    usesMinDays: false,
    charts: [
      { kind: "area", metric: "max_dry_spell", title: "Longest dry spell each year", yLabel: "days",
        trend: true, wide: true, note: "Longest run of days with under 1 mm of rain, within the calendar year." },
      { kind: "diverging", metric: "precip_anomaly_pct", title: "Annual rainfall against the baseline",
        yLabel: "% of 1991–2020 mean", above: "Wetter than normal", below: "Drier than normal" },
      { kind: "combo", metric: "dry_days", title: "Dry days per year", yLabel: "days" },
      { kind: "seasonality", title: "Rainfall through the year" },
      { kind: "lines", series: [{ metric: "dry_spell_count", label: "Dry spells of 20+ days" }],
        title: "Number of long dry spells per year", yLabel: "spells" },
      { kind: "events", title: "Every long dry spell, by year and season", size: "duration",
        sizeLabel: "days", wide: true, note: "Bubble size = length in days. Placed at the start date." },
    ],
    table: {
      title: "Longest dry spells",
      columns: [
        { key: "start", label: "Start" }, { key: "end", label: "End" }, { key: "duration", label: "Days" },
        { key: "precip_total", label: "Rain during spell (mm)" },
      ],
    },
  },

  rainfall: {
    key: "rainfall",
    label: "Heavy rainfall",
    blurb: "Days wetter than the 95th percentile of wet days",
    unit: "days per year",
    question: "Is heavy rain becoming more frequent or more intense?",
    color: "blue",
    eventNoun: "Heavy-rain spells",
    emptyText: "No heavy-rain days detected in this range.",
    usesPercentile: true,
    usesMinDays: false,
    charts: [
      { kind: "combo", metric: "heavy_days", title: "Heavy-rain days per year", yLabel: "days",
        trend: true, wide: true },
      { kind: "stacked", title: "Annual rainfall: heavy days and the rest", yLabel: "mm",
        series: [{ metric: "heavy_precip", label: "On heavy-rain days" },
                 { metric: "other_precip", label: "On other days" }] },
      { kind: "lines", title: "Wettest day and wettest 5 days each year", yLabel: "mm",
        series: [{ metric: "rx1day", label: "Wettest day" }, { metric: "rx5day", label: "Wettest 5 days" }] },
      { kind: "area", metric: "heavy_share_pct", title: "Share of the year's rain that fell on heavy days",
        yLabel: "% of annual rainfall" },
      { kind: "seasonality", title: "When in the year heavy rain falls" },
      { kind: "events", title: "Every heavy-rain spell, by year and season", size: "total_precip",
        sizeLabel: "mm", wide: true, note: "Bubble size = total rain in the spell." },
    ],
    table: {
      title: "Wettest heavy-rain spells",
      columns: [
        { key: "start", label: "Start" }, { key: "end", label: "End" }, { key: "duration", label: "Days" },
        { key: "total_precip", label: "Total rain (mm)" }, { key: "peak_daily", label: "Wettest day (mm)" },
      ],
    },
  },
};

export const HAZARD_LIST = Object.values(HAZARD_VIEWS);
