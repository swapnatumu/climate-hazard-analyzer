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

export interface YearRow {
  year: number;
  complete: boolean;
  event_count: number | null;
  heatwave_days: number | null;
  mean_duration: number | null;
  max_duration: number | null;
  mean_intensity: number | null;
  peak_tmax: number | null;
  excess_heat: number | null;
  rolling_mean: number | null;
  trend_line: number | null;
}

export interface HazardEvent {
  start: string;
  end: string;
  duration: number;
  peak_tmax: number;
  mean_exceedance: number;
  excess_heat: number;
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
  threshold: { value: number; unit: string; mode: string; baseline: [number, number]; percentile: number };
  primary_metric: string;
  yearly: YearRow[];
  top_events: HazardEvent[];
  event_total: number;
  trend: Trend;
  insight: string;
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
