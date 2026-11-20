import { useId } from "react";
import { CURRENCIES } from "../../state/currency";
import type { Currency } from "../../state/currency";

export interface CurrencySwitchProps {
  currency: Currency;
  onSelect: (currency: Currency) => void;
}

/** What the euro view changes: a tooltip on the label, and hidden text for screen readers. */
export const CURRENCY_NOTE = "Returns, factors and cash in EUR. US bond lines are hedged to EUR.";

/**
 * The reference currency as a USD | EUR segmented control under the mode switch, built like the
 * mode switch (native radios, so arrow keys work). In the euro view the label has a dotted underline
 * and shows what changes on mouse-over (title); screen readers read it as the description of the group.
 */
export function CurrencySwitch({ currency, onSelect }: CurrencySwitchProps) {
  const labelId = useId();
  const noteId = useId();
  const note = currency === "EUR" ? CURRENCY_NOTE : null;
  return (
    <>
      <div className="ccy-row">
        <span
          className={note ? "side-label has-tip" : "side-label"}
          id={labelId}
          title={note ?? undefined}
        >
          Currency
        </span>
        {note ? (
          <span className="vh" id={noteId}>
            {note}
          </span>
        ) : null}
        <span
          className="seg-range ccy-seg"
          role="radiogroup"
          aria-labelledby={labelId}
          aria-describedby={note ? noteId : undefined}
        >
          {CURRENCIES.map((value) => (
            <label key={value} className="seg-opt">
              <input type="radio" name="ccy" value={value} checked={currency === value} onChange={() => onSelect(value)} />
              <span>{value}</span>
            </label>
          ))}
        </span>
      </div>
    </>
  );
}
