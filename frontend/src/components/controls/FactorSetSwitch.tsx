import { useId } from "react";
import { FACTOR_SETS, FACTOR_SET_LABELS } from "../../state/factorSet";
import type { FactorSet } from "../../state/factorSet";

export interface FactorSetSwitchProps {
  factorSet: FactorSet;
  onSelect: (factorSet: FactorSet) => void;
}

/** What the Europe set changes: a tooltip on the label, and hidden text for screen readers. */
export const FACTOR_SET_NOTE =
  "Factors: Developed Europe, five factors plus momentum. Macro, energy and world beta keep their US inputs.";

/**
 * The factor set as a US | Europe segmented control, a second row under the currency row. Built like
 * the currency switch (native radios, so the arrow keys work). With the Europe set the label has a
 * dotted underline and shows what changes on mouse-over (title); the group is described by hidden text for screen readers.
 */
export function FactorSetSwitch({ factorSet, onSelect }: FactorSetSwitchProps) {
  const labelId = useId();
  const noteId = useId();
  const note = factorSet === "europe" ? FACTOR_SET_NOTE : null;
  return (
    <>
      <div className="fs-row">
        <span
          className={note ? "side-label has-tip" : "side-label"}
          id={labelId}
          title={note ?? undefined}
        >
          Factor set
        </span>
        {note ? (
          <span className="vh" id={noteId}>
            {note}
          </span>
        ) : null}
        <span
          className="seg-range fs-seg"
          role="radiogroup"
          aria-labelledby={labelId}
          aria-describedby={note ? noteId : undefined}
        >
          {FACTOR_SETS.map((value) => (
            <label key={value} className="seg-opt">
              <input type="radio" name="fs" value={value} checked={factorSet === value} onChange={() => onSelect(value)} />
              <span>{FACTOR_SET_LABELS[value]}</span>
            </label>
          ))}
        </span>
      </div>
    </>
  );
}
