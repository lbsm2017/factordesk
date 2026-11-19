import type { Mode } from "../../state/url";

export interface ModeSwitchProps {
  mode: Mode;
  onSelect: (mode: Mode) => void;
}

const MODES: readonly (readonly [Mode, string])[] = [
  ["ticker", "Ticker"],
  ["track", "Track record"],
  ["portfolio", "Portfolio"],
];

/**
 * The mode of the page as a segmented control, built like the date-range presets: native radios in a
 * fieldset with a visible legend, so arrow keys work. Ticker is the default; Track record is `m=track` and Portfolio is `m=portfolio`.
 */
export function ModeSwitch({ mode, onSelect }: ModeSwitchProps) {
  return (
    <div className="side-group">
      <fieldset className="ctl-range">
        <legend className="side-label">Analyse</legend>
        <span className="seg-range">
          {MODES.map(([value, label]) => (
            <label key={value} className="seg-opt">
              <input type="radio" name="mode" value={value} checked={mode === value} onChange={() => onSelect(value)} />
              <span>{label}</span>
            </label>
          ))}
        </span>
      </fieldset>
    </div>
  );
}
