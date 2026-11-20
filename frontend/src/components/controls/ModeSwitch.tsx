import type { Currency } from "../../state/currency";
import type { FactorSet } from "../../state/factorSet";
import type { Mode } from "../../state/url";
import { CurrencySwitch } from "./CurrencySwitch";
import { FactorSetSwitch } from "./FactorSetSwitch";

export interface ModeSwitchProps {
  mode: Mode;
  onSelect: (mode: Mode) => void;
  /** The reference currency and its setter: the USD | EUR switch sits under the mode switch. */
  currency?: Currency;
  onCurrency?: (currency: Currency) => void;
  /** The factor set and its setter: the US | Europe switch is the second row under the currency. */
  factorSet?: FactorSet;
  onFactorSet?: (factorSet: FactorSet) => void;
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
export function ModeSwitch({ mode, onSelect, currency, onCurrency, factorSet, onFactorSet }: ModeSwitchProps) {
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
      {currency !== undefined && onCurrency !== undefined ? <CurrencySwitch currency={currency} onSelect={onCurrency} /> : null}
      {factorSet !== undefined && onFactorSet !== undefined ? <FactorSetSwitch factorSet={factorSet} onSelect={onFactorSet} /> : null}
    </div>
  );
}
