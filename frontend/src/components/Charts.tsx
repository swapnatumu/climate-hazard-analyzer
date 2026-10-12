import {
  BarController, BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale,
  LineController, LineElement, PointElement, Tooltip, type ChartData, type ChartOptions,
} from "chart.js";
import { Chart } from "react-chartjs-2";
import type { YearRow } from "../types";

ChartJS.register(BarController, BarElement, LineController, LineElement, PointElement,
  CategoryScale, LinearScale, Tooltip, Legend);

type Metric = "event_count" | "heatwave_days" | "mean_intensity" | "excess_heat";

const COLORS = { bar: "#e8743b", rolling: "#1f4e79", trend: "#6b6b6b" };

function rollingOf(rows: YearRow[], metric: Metric): (number | null)[] {
  // Backend gives rolling/trend only for the primary metric; compute a 5-year centred mean here.
  return rows.map((_, i) => {
    const w = rows.slice(i - 2, i + 3);
    if (i < 2 || i > rows.length - 3 || w.some((r) => r[metric] === null)) return null;
    return w.reduce((s, r) => s + (r[metric] as number), 0) / 5;
  });
}

interface Props {
  rows: YearRow[];
  metric: Metric;
  title: string;
  yLabel: string;
  showTrend?: boolean;
}

export function HazardChart({ rows, metric, title, yLabel, showTrend }: Props) {
  const data: ChartData<"bar" | "line", (number | null)[], number> = {
    labels: rows.map((r) => r.year),
    datasets: [
      { type: "bar", label: title, data: rows.map((r) => r[metric]), backgroundColor: COLORS.bar, order: 3 },
      { type: "line", label: "5-yr rolling mean", data: rollingOf(rows, metric), borderColor: COLORS.rolling,
        backgroundColor: COLORS.rolling, pointRadius: 0, borderWidth: 2, spanGaps: false, order: 1 },
      ...(showTrend ? [{ type: "line" as const, label: "Sen's slope trend", data: rows.map((r) => r.trend_line),
        borderColor: COLORS.trend, borderDash: [6, 4], pointRadius: 0, borderWidth: 2, order: 2 }] : []),
    ],
  };
  const options: ChartOptions<"bar" | "line"> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "bottom" },
      tooltip: {
        callbacks: {
          afterTitle: (items) => (rows[items[0].dataIndex]?.complete ? "" : "Incomplete year (excluded)"),
        },
      },
    },
    scales: { y: { beginAtZero: true, title: { display: true, text: yLabel } } },
  };
  return (
    <section className="card chart">
      <h3>{title}</h3>
      <div className="chart-box">
        <Chart type="bar" data={data} options={options} aria-label={title} role="img" />
      </div>
    </section>
  );
}
