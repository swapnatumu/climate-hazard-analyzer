import {
  BarController, BarElement, BubbleController, CategoryScale, Chart as ChartJS, Filler, Legend,
  LinearScale, LineController, LineElement, PointElement, Tooltip,
  type ChartData, type ChartDataset, type ChartOptions,
} from "chart.js";
import { Chart } from "react-chartjs-2";
import type { ChartSpec, HazardView } from "../hazardViews";
import { useChartColors, type ChartColors } from "../theme";
import type { AnalysisResult, HazardEvent, Seasonality, YearRow } from "../types";

ChartJS.defaults.font.family = 'Inter, system-ui, sans-serif';
ChartJS.register(BarController, BarElement, BubbleController, LineController, LineElement,
  PointElement, CategoryScale, LinearScale, Tooltip, Legend, Filler);

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_START_DOY = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];

type YearDataset = ChartDataset<"bar" | "line", (number | null)[]>;

const num = (r: YearRow, metric: string): number | null => {
  const v = r[metric];
  return typeof v === "number" ? v : null;
};

/** 5-year centred mean, computed here because the API sends it only for the primary metric. */
function rollingOf(rows: YearRow[], metric: string): (number | null)[] {
  return rows.map((_, i) => {
    if (i < 2 || i > rows.length - 3) return null;
    const w = rows.slice(i - 2, i + 3).map((r) => num(r, metric));
    return w.some((v) => v === null) ? null : (w as number[]).reduce((s, v) => s + v, 0) / 5;
  });
}

// Ink and grey carry the derived lines (rolling mean, trend, threshold) so they never
// compete with the data colour.
const rollingLine = (rows: YearRow[], metric: string, c: ChartColors): YearDataset => ({
  type: "line", label: "5-year rolling mean", data: rollingOf(rows, metric), borderColor: c.ink,
  backgroundColor: c.ink, pointRadius: 0, borderWidth: 2, spanGaps: false, order: 1,
});

const trendLine = (rows: YearRow[], c: ChartColors): YearDataset => ({
  type: "line", label: "Trend (Sen's slope)", data: rows.map((r) => r.trend_line), borderColor: c.grey,
  backgroundColor: c.grey, borderDash: [6, 4], pointRadius: 0, borderWidth: 2, order: 2,
});

function yearDatasets(spec: ChartSpec, rows: YearRow[], view: HazardView, threshold: number,
                      c: ChartColors): YearDataset[] {
  const main = c[view.color];
  switch (spec.kind) {
    case "combo":
      return [
        { type: "bar", label: "Yearly value", data: rows.map((r) => num(r, spec.metric)),
          backgroundColor: main, borderRadius: 3, order: 3 },
        rollingLine(rows, spec.metric, c),
        ...(spec.trend ? [trendLine(rows, c)] : []),
      ];
    case "area":
      return [
        { type: "line", label: "Yearly value", data: rows.map((r) => num(r, spec.metric)),
          borderColor: main, backgroundColor: `${main}33`, fill: "origin", tension: 0.25,
          pointRadius: 2, pointHoverRadius: 5, borderWidth: 2, order: 3 },
        rollingLine(rows, spec.metric, c),
        ...(spec.trend ? [trendLine(rows, c)] : []),
      ];
    case "lines": {
      const colors = spec.series.length === 1 ? [main] : [c.blue, c.orange];
      return [
        ...spec.series.map((s, i): YearDataset => ({
          type: "line", label: s.label, data: rows.map((r) => num(r, s.metric)), borderColor: colors[i],
          backgroundColor: colors[i], pointRadius: 4, pointHoverRadius: 6, borderWidth: 2, tension: 0.2,
        })),
        ...(spec.threshold ? [{
          type: "line" as const, label: spec.threshold, data: rows.map(() => threshold), borderColor: c.grey,
          backgroundColor: c.grey, borderDash: [6, 4], pointRadius: 0, borderWidth: 2,
        }] : []),
      ];
    }
    case "diverging": {
      const data = rows.map((r) => num(r, spec.metric));
      return [{ type: "bar", label: spec.title, data, borderRadius: 3,
        backgroundColor: data.map((v) => ((v ?? 0) >= 0 ? c.blue : c.orange)) }];
    }
    case "stacked":
      return spec.series.map((s, i): YearDataset => ({
        type: "bar", label: s.label, data: rows.map((r) => num(r, s.metric)), stack: "total",
        backgroundColor: i === 0 ? c.blue : c.blueTint, borderColor: c.surface, borderWidth: { top: 2 },
      }));
    default:
      return [];
  }
}

function YearChart({ spec, rows, view, threshold }: {
  spec: Exclude<ChartSpec, { kind: "events" | "seasonality" }>;
  rows: YearRow[]; view: HazardView; threshold: number;
}) {
  const c = useChartColors();
  const datasets = yearDatasets(spec, rows, view, threshold, c);
  const data: ChartData<"bar" | "line", (number | null)[], number> = { labels: rows.map((r) => r.year), datasets };
  const stacked = spec.kind === "stacked";
  const options: ChartOptions<"bar" | "line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      // One series is named by the title; the diverging chart has its own two-colour key.
      legend: { display: datasets.length > 1, position: "bottom", labels: { boxWidth: 14, color: c.text } },
      tooltip: {
        callbacks: {
          afterTitle: (items) => (rows[items[0].dataIndex]?.complete ? "" : "Incomplete year (excluded)"),
        },
      },
    },
    scales: {
      x: { stacked, grid: { display: false }, ticks: { color: c.text } },
      y: {
        stacked,
        ticks: { color: c.text },
        // A temperature axis starting at 0 °C would flatten the differences that matter.
        beginAtZero: !(spec.kind === "lines" && spec.threshold),
        title: { display: true, text: spec.yLabel, color: c.text },
        grid: { color: c.grid },
      },
    },
  };
  return (
    <>
      {spec.kind === "diverging" && (
        <p className="key small">
          <span><i style={{ background: c.blue }} />{spec.above}</span>
          <span><i style={{ background: c.orange }} />{spec.below}</span>
        </p>
      )}
      <div className="chart-box">
        <Chart type="bar" data={data} options={options} aria-label={spec.title} role="img" />
      </div>
    </>
  );
}

function dayOfYear(iso: string): { year: number; doy: number } {
  const d = new Date(`${iso}T00:00:00Z`);
  const year = d.getUTCFullYear();
  return { year, doy: Math.floor((d.getTime() - Date.UTC(year, 0, 1)) / 86_400_000) + 1 };
}

function EventsChart({ spec, events, view, range }: {
  spec: Extract<ChartSpec, { kind: "events" }>; events: HazardEvent[]; view: HazardView; range: [number, number];
}) {
  const c = useChartColors();
  const main = c[view.color];
  const sizes = events.map((e) => Number(e[spec.size]));
  const max = Math.max(...sizes, 1);
  const data: ChartData<"bubble"> = {
    datasets: [{
      label: view.eventNoun,
      data: events.map((e, i) => {
        const { year, doy } = dayOfYear(e.start);
        // Area, not radius, scales with the value, so big events are not exaggerated.
        return { x: year + (doy - 1) / 366, y: doy, r: 3 + 11 * Math.sqrt(sizes[i] / max) };
      }),
      backgroundColor: `${main}66`,
      borderColor: main,
      borderWidth: 1,
    }],
  };
  const options: ChartOptions<"bubble"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (item) => {
            const e = events[item.dataIndex];
            const extra = spec.size === "duration" ? "" : `, ${e[spec.size]} ${spec.sizeLabel}`;
            return `${e.start} to ${e.end}: ${e.duration} day${e.duration === 1 ? "" : "s"}${extra}`;
          },
        },
      },
    },
    scales: {
      x: { type: "linear", min: range[0], max: range[1] + 1, grid: { color: c.grid },
        ticks: { precision: 0, color: c.text, callback: (v) => String(v) },
        title: { display: true, text: "Year", color: c.text } },
      y: { type: "linear", min: 1, max: 366, grid: { color: c.grid },
        afterBuildTicks: (axis) => { axis.ticks = MONTH_START_DOY.map((value) => ({ value })); },
        ticks: { color: c.text, callback: (v) => MONTHS[MONTH_START_DOY.indexOf(Number(v))] ?? "" },
        title: { display: true, text: "Start date", color: c.text } },
    },
  };
  return (
    <div className="chart-box tall">
      <Chart type="bubble" data={data} options={options} aria-label={spec.title} role="img" />
    </div>
  );
}

function SeasonalityChart({ s, title }: { s: Seasonality; title: string }) {
  const c = useChartColors();
  const colors = [c.blue, c.orange];
  const data: ChartData<"line", (number | null)[], string> = {
    labels: MONTHS,
    datasets: s.periods.map((p, i) => ({
      label: p.label, data: p.values, borderColor: colors[i], backgroundColor: colors[i],
      pointRadius: 4, pointHoverRadius: 6, borderWidth: 2, tension: 0.3,
    })),
  };
  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { position: "bottom", labels: { boxWidth: 14, color: c.text } } },
    scales: {
      x: { grid: { display: false }, ticks: { color: c.text } },
      y: { beginAtZero: true, ticks: { color: c.text },
        title: { display: true, text: s.unit, color: c.text }, grid: { color: c.grid } },
    },
  };
  return (
    <div className="chart-box">
      <Chart type="line" data={data} options={options} aria-label={title} role="img" />
    </div>
  );
}

export function HazardCharts({ result, view }: { result: AnalysisResult; view: HazardView }) {
  return (
    <div className="chart-grid">
      {view.charts.map((spec) => {
        let body;
        let note = spec.note;
        if (spec.kind === "events") {
          if (result.events.length === 0) return null;
          body = <EventsChart spec={spec} events={result.events} view={view} range={result.range} />;
        } else if (spec.kind === "seasonality") {
          if (!result.seasonality) return null;
          note = `${result.seasonality.title}: average for the first and second half of the range.`;
          body = <SeasonalityChart s={result.seasonality} title={spec.title} />;
        } else {
          body = <YearChart spec={spec} rows={result.yearly} view={view} threshold={result.threshold.value} />;
        }
        return (
          <section key={spec.title} className={spec.wide ? "card chart wide" : "card chart"}>
            <h3>{spec.title}</h3>
            {note && <p className="muted small note">{note}</p>}
            {body}
          </section>
        );
      })}
    </div>
  );
}
