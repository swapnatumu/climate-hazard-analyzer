import { HAZARD_LIST } from "../hazardViews";
import { HAZARD_ICONS } from "./Icons";

export function HazardPicker({ value, onChange }: { value: string; onChange: (key: string) => void }) {
  return (
    <fieldset className="panel">
      <legend>Hazard</legend>
      <div className="hazards" role="radiogroup" aria-label="Hazard">
        {HAZARD_LIST.map((h) => {
          const Icon = HAZARD_ICONS[h.key];
          return (
            <button key={h.key} type="button" role="radio" aria-checked={value === h.key} data-hazard={h.key}
              className={value === h.key ? "hazard active" : "hazard"} onClick={() => onChange(h.key)}>
              <span className="hazard-icon"><Icon /></span>
              <span>
                <strong>{h.label}</strong>
                <span className="muted small">{h.blurb}</span>
              </span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
