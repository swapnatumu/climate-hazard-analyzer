import type { HazardView } from "../hazardViews";
import type { HazardEvent } from "../types";

export function TopEvents({ events, view }: { events: HazardEvent[]; view: HazardView }) {
  if (events.length === 0) return null;
  const { title, columns } = view.table;
  return (
    <section className="card">
      <h3>{title}</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>{columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.start}>{columns.map((c) => <td key={c.key}>{e[c.key]}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
