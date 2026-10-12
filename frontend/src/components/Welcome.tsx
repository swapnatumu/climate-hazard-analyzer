import { HAZARD_VIEWS } from "../hazardViews";
import type { Region } from "../types";
import { HAZARD_ICONS } from "./Icons";

const EXAMPLES: { hazard: string; region: Region }[] = [
  { hazard: "heatwave", region: { kind: "point", lat: 17.385, lon: 78.487, label: "Hyderabad, Telangana" } },
  { hazard: "rainfall", region: { kind: "point", lat: 17.687, lon: 83.219, label: "Visakhapatnam, Andhra Pradesh" } },
  { hazard: "drought", region: { kind: "point", lat: 14.682, lon: 77.601, label: "Anantapur, Andhra Pradesh" } },
];

const STEPS = [
  ["Pick a place", "Choose a preset, search a city, or click the map. A box averages up to 25 grid cells."],
  ["Pick a hazard and years", "Thresholds come from a fixed 1991–2020 baseline, so results stay comparable when the range changes."],
  ["Read the trend honestly", "A change is called an increase or decrease only when the Mann-Kendall test finds it significant."],
];

export function Welcome({ onExample }: { onExample: (hazard: string, region: Region) => void }) {
  return (
    <section className="card welcome">
      <h2>What has changed where you live?</h2>
      <p className="muted">
        Eighty years of daily weather from the ERA5 reanalysis, turned into yearly counts of heatwaves,
        dry spells and heavy-rain days, with a trend test that says when a change is real.
      </p>
      <ol className="steps">
        {STEPS.map(([title, text]) => (
          <li key={title}><strong>{title}</strong><span className="muted small">{text}</span></li>
        ))}
      </ol>
      <p className="tile-label">Or start from an example</p>
      <div className="examples">
        {EXAMPLES.map(({ hazard, region }) => {
          const Icon = HAZARD_ICONS[hazard];
          return (
            <button key={hazard} type="button" className="example" data-hazard={hazard}
              onClick={() => onExample(hazard, region)}>
              <span className="hazard-icon"><Icon /></span>
              <span><strong>{HAZARD_VIEWS[hazard].label}</strong><span className="muted small">{region.label}</span></span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
