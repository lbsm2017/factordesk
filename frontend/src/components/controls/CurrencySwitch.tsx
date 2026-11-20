import { useId } from "react";
import { CURRENCIES } from "../../state/currency";
import type { Currency } from "../../state/currency";

export interface CurrencySwitchProps {
  currency: Currency;
  onSelect: (currency: Currency) => void;
}

/**
 * The reference currency as a USD | EUR segmented control under the mode switch, built like the
 * mode switch (native radios, so arrow keys work). In the euro view a short note says what changes.
 */
export function CurrencySwitch({ currency, onSelect }: CurrencySwitchProps) {
  const labelId = useId();
  return (
    <>
      <div className="ccy-row">
        <span className="side-label" id={labelId}>
          Currency
        </span>
        <span className="seg-range ccy-seg" role="radiogroup" aria-labelledby={labelId}>
          {CURRENCIES.map((value) => (
            <label key={value} className="seg-opt">
              <input type="radio" name="ccy" value={value} checked={currency === value} onChange={() => onSelect(value)} />
              <span>{value}</span>
            </label>
          ))}
        </span>
      </div>
      {currency === "EUR" ? (
        <p className="side-note ccy-note">
          Returns, factors and cash in <b>EUR</b>. US bond lines are hedged to EUR.
        </p>
      ) : null}
    </>
  );
}
