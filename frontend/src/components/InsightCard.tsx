import type { AnalysisResult } from "../types";

export function InsightCard({ r }: { r: AnalysisResult }) {
  const t = r.trend;
  const badge = t.significant ? (t.direction === "increasing" ? "up" : "down") : "flat";
  return (
    <section className="card insight">
      <p className={`badge ${badge}`}>
        {t.significant ? `Significant ${t.direction} trend` : "No significant trend"}
      </p>
      <p className="sentence">{r.insight}</p>
      <dl className="meta">
        <div><dt>Threshold</dt><dd>{r.threshold.value} {r.threshold.unit} (p{r.threshold.percentile} of daily Tmax)</dd></div>
        <div><dt>Baseline</dt><dd>{r.threshold.baseline[0]}–{r.threshold.baseline[1]}</dd></div>
        <div><dt>Method</dt><dd>Mann-Kendall + Sen's slope</dd></div>
        <div><dt>p-value</dt><dd>{t.p_value < 0.001 ? "< 0.001" : t.p_value.toFixed(3)}</dd></div>
        <div><dt>Events in range</dt><dd>{r.event_total}</dd></div>
        <div><dt>Grid cell</dt><dd>{r.region.type === "point"
          ? `${r.region.cell.lat}, ${r.region.cell.lon}` : `${r.region.cells} cells averaged`}</dd></div>
      </dl>
      {r.caveats.length > 0 && (
        <ul className="caveats">{r.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
      )}
    </section>
  );
}
