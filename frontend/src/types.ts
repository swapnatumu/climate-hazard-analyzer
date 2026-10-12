// Mirrors backend response shapes (backend/app/services/analysis.py).

export type Region =
  | { kind: "point"; lat: number; lon: number; label: string }
  | { kind: "bbox"; minLon: number; minLat: number; maxLon: number; maxLat: number; label: string };

export interface AnalysisParams {
  hazard: string;
  region: Region;
  start: number;
  end: number;
  percentile: number;
  minDays: number;
}

/** One row per year. Metric columns depend on the hazard (see hazardViews.ts). */
export interface YearRow {
  year: number;
  complete: boolean;
  rolling_mean: number | null;
  trend_line: number | null;
  [metric: string]: number | boolean | null;
}

/** Start/end/duration plus hazard-specific metrics (e.g. excess_heat, total_precip). */
export interface HazardEvent {
  start: string;
  end: string;
  duration: number;
  [metric: string]: number | string;
}

export interface Seasonality {
  title: string;
  unit: string;
  periods: { label: string; values: (number | null)[] }[];
}

export interface Trend {
  method: string;
  n_years: number;
  slope_per_decade: number;
  p_value: number;
  significant: boolean;
  direction: "increasing" | "decreasing" | "no trend";
  ols_slope_per_decade: number;
}

export interface AnalysisResult {
  id: string;
  hazard: string;
  region:
    | { type: "point"; cell: { lat: number; lon: number }; requested: { lat: number; lon: number } }
    | { type: "bbox"; bbox: [number, number, number, number]; cells: number };
  range: [number, number];
  threshold: {
    value: number; unit: string; mode: string; baseline: [number, number];
    percentile: number | null; description: string; reference: Record<string, number>;
  };
  primary_metric: string;
  yearly: YearRow[];
  top_events: HazardEvent[];
  events: HazardEvent[];
  seasonality: Seasonality | null;
  event_total: number;
  trend: Trend;
  insight: string;
  /** The two values the insight sentence compares. */
  comparison: {
    basis: "decade_means" | "trend_line";
    start_label: string; start_value: number; end_label: string; end_value: number;
  };
  caveats: string[];
  source: string;
  algo_version: string;
  computed_at: string;
  cache: "hit" | "miss";
}

export interface GeocodeResult {
  name: string;
  admin1: string | null;
  country: string | null;
  lat: number;
  lon: number;
}

export interface HazardInfo {
  key: string;
  label: string;
  defaults: { percentile: number; min_days: number; threshold_mode: string };
}

export interface ApiErrorBody {
  error: { code: string; message: string };
}

export interface PresetCity { id: string; name: string; state: string; lat: number; lon: number }
export interface PresetArea { id: string; name: string; state: string; bbox: [number, number, number, number] }
