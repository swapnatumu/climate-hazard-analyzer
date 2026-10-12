import type {
  AnalysisParams, AnalysisResult, ApiErrorBody, GeocodeResult, HazardInfo, PresetArea, PresetCity,
} from "../types";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function getJson<T>(path: string, params?: URLSearchParams, signal?: AbortSignal): Promise<T> {
  const url = `${API_BASE}${path}${params ? `?${params}` : ""}`;
  let res: Response;
  try {
    res = await fetch(url, { signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "NETWORK", "Cannot reach the server. It may be waking up; try again.");
  }
  if (!res.ok) {
    let body: ApiErrorBody | undefined;
    try {
      body = await res.json();
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, body?.error.code ?? "HTTP_ERROR", body?.error.message ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export function analysisSearchParams(p: AnalysisParams): URLSearchParams {
  const q = new URLSearchParams({
    start: String(p.start),
    end: String(p.end),
    percentile: String(p.percentile),
    min_days: String(p.minDays),
  });
  if (p.region.kind === "point") {
    q.set("lat", p.region.lat.toFixed(4));
    q.set("lon", p.region.lon.toFixed(4));
  } else {
    const r = p.region;
    q.set("bbox", [r.minLon, r.minLat, r.maxLon, r.maxLat].join(","));
  }
  return q;
}

export const api = {
  hazards: () =>
    getJson<{ hazards: HazardInfo[]; baseline: [number, number]; default: string }>("/api/hazards"),
  analyze: (p: AnalysisParams, signal?: AbortSignal) =>
    getJson<AnalysisResult>(`/api/hazards/${encodeURIComponent(p.hazard)}`, analysisSearchParams(p), signal),
  regions: () => getJson<{ cities: PresetCity[]; areas: PresetArea[] }>("/api/regions"),
  geocode: (q: string, signal?: AbortSignal) =>
    getJson<{ results: GeocodeResult[] }>("/api/geocode", new URLSearchParams({ q }), signal),
  csvUrl: (p: AnalysisParams) =>
    `${API_BASE}/api/hazards/${encodeURIComponent(p.hazard)}/export.csv?${analysisSearchParams(p)}`,
};
