import type { HazardEvent } from "../types";

export function TopEvents({ events }: { events: HazardEvent[] }) {
  if (events.length === 0) return null;
  return (
    <section className="card">
      <h3>Top {events.length} heatwaves by excess heat</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Start</th><th>End</th><th>Days</th><th>Peak Tmax (°C)</th>
              <th>Mean exceedance (°C)</th><th>Excess heat (°C·days)</th></tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.start}>
                <td>{e.start}</td><td>{e.end}</td><td>{e.duration}</td><td>{e.peak_tmax}</td>
                <td>{e.mean_exceedance}</td><td>{e.excess_heat}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
