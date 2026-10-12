import { useState } from "react";
import { api } from "./api/client";
import { HazardChart } from "./components/Charts";
import { InsightCard } from "./components/InsightCard";
import { RegionPicker } from "./components/RegionPicker";
import { TopEvents } from "./components/TopEvents";
import { useHazard } from "./hooks/useHazard";
import type { AnalysisParams, Region } from "./types";

const MIN_YEAR = 1940;
const LAST_COMPLETE_YEAR = new Date().getFullYear() - 1;
const HAZARDS = [{ key: "heatwave", label: "Heatwave" }]; // drought / rainfall: stretch goals

export default function App() {
  const [region, setRegion] = useState<Region | null>(null);
  const [hazard, setHazard] = useState("heatwave");
  const [start, setStart] = useState(1990);
  const [end, setEnd] = useState(Math.min(2020, LAST_COMPLETE_YEAR));
  const [percentile, setPercentile] = useState(95);
  const [minDays, setMinDays] = useState(3);
  const [submitted, setSubmitted] = useState<AnalysisParams | null>(null);

  const rangeError = end - start + 1 < 10 ? "Pick a range of at least 10 years." : null;
  const { data, error, isFetching, waking, refetch } = useHazard(submitted);

  const run = () => {
    if (region && !rangeError) setSubmitted({ hazard, region, start, end, percentile, minDays });
  };

  return (
    <div className="layout">
      <header>
        <h1>Climate Hazard Trend Analyzer</h1>
        <p className="muted">How have heatwaves changed in a place over time?</p>
      </header>

      <aside>
        <RegionPicker value={region} onChange={setRegion} />

        <fieldset className="panel">
          <legend>Hazard</legend>
          <select value={hazard} onChange={(e) => setHazard(e.target.value)}>
            {HAZARDS.map((h) => <option key={h.key} value={h.key}>{h.label}</option>)}
          </select>
        </fieldset>

        <fieldset className="panel">
          <legend>Years: {start}–{end}</legend>
          <label>From
            <input type="range" min={MIN_YEAR} max={LAST_COMPLETE_YEAR - 9} value={start}
              onChange={(e) => setStart(Math.min(Number(e.target.value), end - 9))} />
          </label>
          <label>To
            <input type="range" min={MIN_YEAR + 9} max={LAST_COMPLETE_YEAR} value={end}
              onChange={(e) => setEnd(Math.max(Number(e.target.value), start + 9))} />
          </label>
          {rangeError && <p className="error small">{rangeError}</p>}
        </fieldset>

        <details className="panel">
          <summary>Advanced</summary>
          <label>Percentile threshold
            <select value={percentile} onChange={(e) => setPercentile(Number(e.target.value))}>
              {[90, 95, 97, 99].map((p) => <option key={p} value={p}>{p}th</option>)}
            </select>
          </label>
          <label>Minimum consecutive days
            <select value={minDays} onChange={(e) => setMinDays(Number(e.target.value))}>
              {[2, 3, 4, 5, 6, 7].map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <p className="muted small">Threshold uses the fixed 1991–2020 baseline, so it doesn't move with the year range.</p>
        </details>

        <button className="primary" type="button" disabled={!region || !!rangeError || isFetching} onClick={run}>
          {isFetching ? "Analyzing…" : "Analyze"}
        </button>
      </aside>

      <main>
        {!submitted && <div className="card empty">Pick a region and a year range, then press Analyze.</div>}

        {isFetching && (
          <div className="card status" role="status">
            {waking
              ? "Waking up the server and fetching decades of daily data. The first request for a new place can take up to a minute."
              : "Analyzing…"}
          </div>
        )}

        {error && !isFetching && (
          <div className="card error" role="alert">
            <p>{(error as Error).message}</p>
            <button type="button" onClick={() => refetch()}>Retry</button>
          </div>
        )}

        {data && !isFetching && (
          <>
            <InsightCard r={data} />
            {data.event_total === 0 && <div className="card empty">No heatwaves detected in this range.</div>}
            <HazardChart rows={data.yearly} metric="event_count" title="Heatwave events per year"
              yLabel="events" showTrend />
            <HazardChart rows={data.yearly} metric="heatwave_days" title="Heatwave days per year" yLabel="days" />
            <HazardChart rows={data.yearly} metric="excess_heat" title="Excess heat per year"
              yLabel="°C·days above threshold" />
            <TopEvents events={data.top_events} />
            <div className="actions">
              <a className="button" href={api.csvUrl(submitted!)} download>Download CSV</a>
            </div>
          </>
        )}
      </main>

      <footer className="muted small">
        Weather data by <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo.com</a>,
        licensed under CC BY 4.0. ERA5 data from the Copernicus Climate Change Service.
      </footer>
    </div>
  );
}
