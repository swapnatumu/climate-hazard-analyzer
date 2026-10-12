import type { AnalysisResult } from "../types";

export function InsightCard({ r }: { r: AnalysisResult }) {
  const t = r.trend;
  const normal = r.threshold.reference.mean_annual_precip;
  const badge = t.significant ? (t.direction === "increasing" ? "up" : "down") : "flat";
  return (
    <section className="card insight">
      <p className={`badge ${badge}`}>
        {t.significant ? `Significant ${t.direction} trend` : "No significant trend"}
      </p>
      <p className="sentence">{r.insight}</p>
      <dl className="meta">
        <div><dt>Baseline</dt><dd>{r.threshold.baseline[0]}–{r.threshold.baseline[1]}</dd></div>
        <div><dt>Method</dt><dd>Mann-Kendall + Sen's slope</dd></div>
        <div><dt>Data</dt><dd>ERA5 via Open-Meteo{r.cache === "hit" ? " (cached)" : ""}</dd></div>
        <div><dt>Grid cell</dt><dd>{r.region.type === "point"
          ? `${r.region.cell.lat}, ${r.region.cell.lon}` : `${r.region.cells} cells averaged`}</dd></div>
        {normal !== undefined && <div><dt>Baseline annual rainfall</dt><dd>{normal} mm</dd></div>}
      </dl>
      {r.caveats.length > 0 && (
        <ul className="caveats">{r.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
      )}
    </section>
  );
}
