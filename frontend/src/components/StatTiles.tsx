import { useEffect, useState } from "react";
import type { HazardView } from "../hazardViews";
import type { AnalysisResult } from "../types";

/** Eases a number up from 0 when it changes; jumps straight there under reduced motion. */
function useCountUp(target: number, ms = 800): number {
  const [value, setValue] = useState(target);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setValue(target);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      setValue(target * (1 - (1 - k) ** 3));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return value;
}

function Count({ value, digits = 0 }: { value: number; digits?: number }) {
  return <>{useCountUp(value).toFixed(digits)}</>;
}

export function StatTiles({ r, view }: { r: AnalysisResult; view: HazardView }) {
  const { start_value: a, end_value: b, start_label, end_label, basis } = r.comparison;
  const t = r.trend;
  const sign = b - a >= 0 ? "+" : "−";
  // A percentage of zero is undefined, so fall back to the absolute change.
  const change = a === 0
    ? <>{sign}<Count value={Math.abs(b - a)} digits={1} /></>
    : <>{sign}<Count value={Math.abs((b - a) / a) * 100} />%</>;

  return (
    <section className="tiles" aria-label="Key figures">
      <div className="tile">
        <p className="tile-label">Threshold</p>
        <p className="tile-value"><Count value={r.threshold.value} digits={1} /> <small>{r.threshold.unit}</small></p>
        <p className="tile-sub">{r.threshold.description}</p>
      </div>
      <div className="tile">
        <p className="tile-label">{view.eventNoun}</p>
        <p className="tile-value"><Count value={r.event_total} /></p>
        <p className="tile-sub">{r.range[0]}–{r.range[1]}</p>
      </div>
      <div className="tile">
        <p className="tile-label">{basis === "decade_means" ? "First vs last decade" : "Trend line, start vs end"}</p>
        {/* Greyed when the trend test fails, so the number is not read as a finding. */}
        <p className={t.significant ? "tile-value" : "tile-value tile-quiet"}>{change}</p>
        <p className="tile-sub">{a.toFixed(1)} → {b.toFixed(1)} {view.unit} ({start_label} vs {end_label})</p>
      </div>
      <div className={t.significant ? "tile tile-accent" : "tile"}>
        <p className="tile-label">Trend</p>
        <p className="tile-value tile-text">
          {t.significant ? (t.direction === "increasing" ? "Increasing" : "Decreasing") : "Not significant"}
        </p>
        <p className="tile-sub">
          Mann-Kendall p {t.p_value < 0.001 ? "< 0.001" : `= ${t.p_value.toFixed(3)}`}
          {" · "}{t.slope_per_decade >= 0 ? "+" : "−"}{Math.abs(t.slope_per_decade).toFixed(2)} per decade
        </p>
      </div>
    </section>
  );
}
