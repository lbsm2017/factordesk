import { MODELS } from "../../state/url";
import type { FactorModel } from "../../state/url";

export interface ModelToggleProps {
  selected: FactorModel;
  onSelect: (model: FactorModel) => void;
  /** Nothing is loaded yet: both options are disabled. */
  disabled?: boolean;
}

const LABELS: Record<FactorModel, string> = { ff5: "FF5", ff6: "FF6" };
const TITLES: Record<FactorModel, string> = {
  ff5: "Five Fama-French factors: market, size, value, profitability and investment",
  ff6: "The five factors plus momentum (recent winners minus recent losers)",
};

/**
 * The factor model as a segmented control, with the markup and styles of `RangeChips`: native radios
 * in a fieldset with the visible legend "Factor model", so arrow keys work. FF6 is the dashboard default;
 * FF6 adds momentum. Neither option is marked as better. Not mounted since the owner removed the model
 * selector from the sidebar (2026-11-19); kept for the future Settings module.
 */
export function ModelToggle({ selected, onSelect, disabled = false }: ModelToggleProps) {
  return (
    <fieldset className="ctl-range">
      <legend className="side-label">Factor model</legend>
      <span className="seg-range">
        {MODELS.map((model) => (
          <label key={model} className={disabled ? "seg-opt off" : "seg-opt"} title={TITLES[model]}>
            <input
              type="radio"
              name="model"
              value={model}
              checked={!disabled && selected === model}
              disabled={disabled}
              onChange={() => onSelect(model)}
            />
            <span>{LABELS[model]}</span>
          </label>
        ))}
      </span>
    </fieldset>
  );
}
