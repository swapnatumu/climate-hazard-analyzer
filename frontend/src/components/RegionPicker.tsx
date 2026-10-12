import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { GeocodeResult, Region } from "../types";

type Mode = "preset" | "city" | "point" | "bbox";
const TAB_LABELS: Record<Mode, string> = { preset: "Presets", city: "Search", point: "Lat / Lon", bbox: "Box" };

interface Props {
  value: Region | null;
  onChange: (r: Region) => void;
}

export function RegionPicker({ value, onChange }: Props) {
  const [mode, setMode] = useState<Mode>("preset");

  return (
    <fieldset className="panel">
      <legend>Region</legend>
      <div className="tabs" role="tablist">
        {(Object.keys(TAB_LABELS) as Mode[]).map((m) => (
          <button key={m} type="button" role="tab" aria-selected={mode === m}
            className={mode === m ? "tab active" : "tab"} onClick={() => setMode(m)}>
            {TAB_LABELS[m]}
          </button>
        ))}
      </div>
      {mode === "preset" && <PresetPicker onPick={onChange} />}
      {mode === "city" && <CitySearch onPick={onChange} />}
      {mode === "point" && <PointForm onSubmit={onChange} />}
      {mode === "bbox" && <BboxForm onSubmit={onChange} />}
      {value
        ? <p className="selected small">Selected: {value.label}</p>
        : <p className="muted small">Or click the map to choose a point or draw a box.</p>}
    </fieldset>
  );
}

function PresetPicker({ onPick }: { onPick: (r: Region) => void }) {
  const { data, error } = useQuery({ queryKey: ["regions"], queryFn: api.regions, staleTime: Infinity });
  if (error) return <p className="error small">{(error as Error).message}</p>;
  if (!data) return <p className="muted small">Loading presets…</p>;

  const pick = (value: string) => {
    const [kind, id] = value.split(":");
    if (kind === "city") {
      const c = data.cities.find((x) => x.id === id);
      if (c) onPick({ kind: "point", lat: c.lat, lon: c.lon, label: `${c.name}, ${c.state}` });
    } else {
      const a = data.areas.find((x) => x.id === id);
      if (a) {
        const [minLon, minLat, maxLon, maxLat] = a.bbox;
        onPick({ kind: "bbox", minLon, minLat, maxLon, maxLat, label: `${a.name} (area average)` });
      }
    }
  };

  return (
    <div>
      <select defaultValue="" onChange={(e) => pick(e.target.value)} aria-label="Preset region">
        <option value="" disabled>Choose a city or area…</option>
        {["Telangana", "Andhra Pradesh"].map((state) => (
          <optgroup key={state} label={`${state}: cities`}>
            {data.cities.filter((c) => c.state === state).map((c) => (
              <option key={c.id} value={`city:${c.id}`}>{c.name}</option>
            ))}
          </optgroup>
        ))}
        {["Telangana", "Andhra Pradesh"].map((state) => (
          <optgroup key={`${state}-areas`} label={`${state}: areas`}>
            {data.areas.filter((a) => a.state === state).map((a) => (
              <option key={a.id} value={`area:${a.id}`}>{a.name}</option>
            ))}
          </optgroup>
        ))}
      </select>
      <p className="muted small">Areas are approximate rectangles, not official boundaries.</p>
    </div>
  );
}

function CitySearch({ onPick }: { onPick: (r: Region) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Debounced search; aborts the previous request when the user keeps typing.
  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setResults([]);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      api.geocode(term, ctrl.signal)
        .then((r) => { setResults(r.results); setError(null); })
        .catch((e: Error) => { if (e.name !== "AbortError") setError(e.message); });
    }, 300);
    return () => { clearTimeout(t); ctrl.abort(); };
  }, [q]);

  return (
    <div>
      <input type="search" placeholder="Search a city, e.g. Pune" value={q} maxLength={100}
        onChange={(e) => setQ(e.target.value)} aria-label="City" />
      {error && <p className="error small">{error}</p>}
      {results.length > 0 && (
        <ul className="results">
          {results.map((r) => {
            const label = [r.name, r.admin1, r.country].filter(Boolean).join(", ");
            return (
              <li key={`${r.lat},${r.lon}`}>
                <button type="button" onClick={() => {
                  onPick({ kind: "point", lat: r.lat, lon: r.lon, label });
                  setResults([]);
                  setQ(label);
                }}>
                  {label} <span className="muted small">({r.lat.toFixed(2)}, {r.lon.toFixed(2)})</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function num(v: string): number | null {
  const n = Number(v);
  return v.trim() !== "" && Number.isFinite(n) ? n : null;
}

function PointForm({ onSubmit }: { onSubmit: (r: Region) => void }) {
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const la = num(lat), lo = num(lon);
  const valid = la !== null && lo !== null && Math.abs(la) <= 90 && Math.abs(lo) <= 180;
  return (
    <form className="grid2" onSubmit={(e) => {
      e.preventDefault();
      if (valid) onSubmit({ kind: "point", lat: la!, lon: lo!, label: `${la}, ${lo}` });
    }}>
      <label>Lat<input value={lat} onChange={(e) => setLat(e.target.value)} inputMode="decimal" /></label>
      <label>Lon<input value={lon} onChange={(e) => setLon(e.target.value)} inputMode="decimal" /></label>
      <button type="submit" disabled={!valid}>Use point</button>
    </form>
  );
}

function BboxForm({ onSubmit }: { onSubmit: (r: Region) => void }) {
  const [v, setV] = useState({ minLon: "", minLat: "", maxLon: "", maxLat: "" });
  const n = { minLon: num(v.minLon), minLat: num(v.minLat), maxLon: num(v.maxLon), maxLat: num(v.maxLat) };
  const ok = Object.values(n).every((x) => x !== null)
    && n.minLon! < n.maxLon! && n.minLat! < n.maxLat!
    && n.maxLon! - n.minLon! <= 2 && n.maxLat! - n.minLat! <= 2;
  return (
    <form className="grid2" onSubmit={(e) => {
      e.preventDefault();
      if (ok) onSubmit({ kind: "bbox", minLon: n.minLon!, minLat: n.minLat!, maxLon: n.maxLon!,
        maxLat: n.maxLat!, label: `Box ${v.minLat},${v.minLon} → ${v.maxLat},${v.maxLon}` });
    }}>
      {(Object.keys(v) as (keyof typeof v)[]).map((k) => (
        <label key={k}>{k}<input value={v[k]} inputMode="decimal"
          onChange={(e) => setV({ ...v, [k]: e.target.value })} /></label>
      ))}
      <p className="muted small span2">Max 2° × 2°. Values are averaged over up to 25 grid cells.</p>
      <button type="submit" disabled={!ok}>Use box</button>
    </form>
  );
}
