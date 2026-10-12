import { useEffect, useRef, useState } from "react";
import { api } from "./api/client";
import { HazardCharts } from "./components/Charts";
import { HazardPicker } from "./components/HazardPicker";
import { MoonIcon, SunIcon } from "./components/Icons";
import { InsightCard } from "./components/InsightCard";
import { MapSelector } from "./components/MapSelector";
import { RegionPicker } from "./components/RegionPicker";
import { StatTiles } from "./components/StatTiles";
import { TopEvents } from "./components/TopEvents";
import { Welcome } from "./components/Welcome";
import { HAZARD_VIEWS } from "./hazardViews";
import { useHazard } from "./hooks/useHazard";
import { useTheme } from "./theme";
import type { AnalysisParams, Region } from "./types";

const MIN_YEAR = 1940;
const LAST_COMPLETE_YEAR = new Date().getFullYear() - 1;

export default function App() {
  const { theme, toggle } = useTheme();
  const [region, setRegion] = useState<Region | null>(null);
  const [hazard, setHazard] = useState("heatwave");
  const [start, setStart] = useState(1990);
  const [end, setEnd] = useState(Math.min(2020, LAST_COMPLETE_YEAR));
  const [percentile, setPercentile] = useState(95);
  const [minDays, setMinDays] = useState(3);
  const [submitted, setSubmitted] = useState<AnalysisParams | null>(null);

  const rangeError = end - start + 1 < 10 ? "Pick a range of at least 10 years." : null;
  const { data, error, isFetching, waking, refetch } = useHazard(submitted);
  const picked = HAZARD_VIEWS[hazard];
  const shown = data ? HAZARD_VIEWS[data.hazard] : null;

  const analyze = (h: string, r: Region | null) => {
    if (!r || rangeError) return;
    const next: AnalysisParams = { hazard: h, region: r, start, end, percentile, minDays };
    // Same inputs after a failure: the query key is unchanged, so ask for a refetch.
    if (error && JSON.stringify(next) === JSON.stringify(submitted)) void refetch();
    setSubmitted(next);
  };

  const runExample = (h: string, r: Region) => {
    setHazard(h);
    setRegion(r);
    analyze(h, r);
  };

  // Bring the results into view when a new analysis arrives.
  const resultsRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!data) return;
    const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    resultsRef.current?.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
  }, [data]);

  return (
    <div className="layout" data-hazard={hazard}>
      <header className="top">
        <div>
          <p className="eyebrow">ERA5 reanalysis · {MIN_YEAR}–{LAST_COMPLETE_YEAR}</p>
          <h1>Climate Hazard Trend Analyzer</h1>
          <p className="lede">{picked.question}</p>
        </div>
        <button type="button" className="theme-toggle" onClick={toggle}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </button>
      </header>

      <aside>
        <HazardPicker value={hazard} onChange={setHazard} />
        <RegionPicker value={region} onChange={setRegion} />

        <fieldset className="panel">
          <legend>Years <span className="range-value">{start}–{end}</span></legend>
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
          {picked.usesPercentile && (
            <label>Percentile threshold
              <select value={percentile} onChange={(e) => setPercentile(Number(e.target.value))}>
                {[90, 95, 97, 99].map((p) => <option key={p} value={p}>{p}th</option>)}
              </select>
            </label>
          )}
          {picked.usesMinDays && (
            <label>Minimum consecutive days
              <select value={minDays} onChange={(e) => setMinDays(Number(e.target.value))}>
                {[2, 3, 4, 5, 6, 7].map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
          )}
          <p className="muted small">
            {hazard === "drought"
              ? "A dry day has under 1 mm of rain. Annual rainfall is compared with the fixed 1991–2020 mean."
              : "Threshold uses the fixed 1991–2020 baseline, so it doesn't move with the year range."}
          </p>
        </details>

        <button className="primary" type="button" disabled={!region || !!rangeError || isFetching}
          onClick={() => analyze(hazard, region)}>
          {isFetching ? "Analyzing…" : region ? `Analyze ${picked.label.toLowerCase()}` : "Pick a region first"}
        </button>
      </aside>

      <main>
        <MapSelector value={region} onPick={setRegion} />

        {!submitted && <Welcome onExample={runExample} />}

        <div ref={resultsRef} className="results">
          {isFetching && (
            <div className="reveal" role="status" aria-live="polite">
              <p className="card status">
                {waking
                  ? "Waking up the server and fetching decades of daily data. The first request for a new place can take up to a minute."
                  : "Analyzing…"}
              </p>
              <div className="tiles">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton tile-skeleton" />)}</div>
              <div className="skeleton block-skeleton" />
            </div>
          )}

          {error && !isFetching && (
            <div className="card error-card" role="alert">
              <p>{(error as Error).message}</p>
              <button type="button" onClick={() => refetch()}>Retry</button>
            </div>
          )}

          {data && shown && !isFetching && (
            // Keyed by result id so the entrance animation replays for each new analysis.
            <div key={data.id} className="reveal" data-hazard={data.hazard}>
              <StatTiles r={data} view={shown} />
              <InsightCard r={data} />
              {data.event_total === 0 && <div className="card empty">{shown.emptyText}</div>}
              <HazardCharts result={data} view={shown} />
              <TopEvents events={data.top_events} view={shown} />
              <div className="actions">
                <a className="button" href={api.csvUrl(submitted!)} download>Download CSV</a>
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="muted small">
        Weather data by <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo.com</a>,
        licensed under CC BY 4.0. ERA5 data from the Copernicus Climate Change Service.
      </footer>
    </div>
  );
}
