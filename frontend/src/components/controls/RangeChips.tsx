import type { RangeOption } from "../../api/types";
import { PRESETS } from "../../state/url";
import type { Preset } from "../../state/url";

export interface RangeChipsProps {
  /** From the ranges endpoint; undefined while loading. Render only the presets in PRESETS. */
  options: RangeOption[] | undefined;
  /** Selected preset; null when custom dates are used. */
  selected: Preset | null;
  onSelect: (preset: Preset) => void;
  /** Id of the element that states why a chip is unavailable (visible text under the strip). */
  describedBy?: string;
  /** No ticker is loaded yet: every chip is disabled and none is shown as selected. */
  disabled?: boolean;
}

const LABELS: Record<Preset, string> = { "3Y": "3Y", "5Y": "5Y", "10Y": "10Y", FULL: "Full history" };

/**
 * Range chips (dashboard spec DB6.3): native radios in a fieldset with a hidden legend, so arrow
 * keys work. An unavailable chip is disabled; its reason is shown by the controls strip.
 */
export function RangeChips({ options, selected, onSelect, describedBy, disabled = false }: RangeChipsProps) {
  return (
    <fieldset className="ctl-range" {...(describedBy ? { "aria-describedby": describedBy } : {})}>
      <legend className="vh">Date range</legend>
      <span className="chips">
        {PRESETS.map((preset) => {
          const option = options?.find((o) => o.preset === preset);
          const off = disabled || (option !== undefined && !option.available);
          return (
            <label key={preset} className={off ? "chip-opt off" : "chip-opt"}>
              <input
                type="radio"
                name="range"
                value={preset}
                checked={!disabled && selected === preset}
                disabled={off}
                onChange={() => onSelect(preset)}
              />
              <span>{LABELS[preset]}</span>
            </label>
          );
        })}
      </span>
    </fieldset>
  );
}
