import { useId } from "react";
import { FACTOR_SETS, FACTOR_SET_LABELS } from "../../state/factorSet";
import type { FactorSet } from "../../state/factorSet";

export interface FactorSetSwitchProps {
  factorSet: FactorSet;
  onSelect: (factorSet: FactorSet) => void;
}

/**
 * The factor set as a US | Europe segmented control, a second row under the currency row. Built like
 * the currency switch (native radios, so the arrow keys work). The Europe set adds a short note.
 */
export function FactorSetSwitch({ factorSet, onSelect }: FactorSetSwitchProps) {
  const labelId = useId();
  return (
    <>
      <div className="fs-row">
        <span className="side-label" id={labelId}>
          Factor set
        </span>
        <span className="seg-range fs-seg" role="radiogroup" aria-labelledby={labelId}>
          {FACTOR_SETS.map((value) => (
            <label key={value} className="seg-opt">
              <input type="radio" name="fs" value={value} checked={factorSet === value} onChange={() => onSelect(value)} />
              <span>{FACTOR_SET_LABELS[value]}</span>
            </label>
          ))}
        </span>
      </div>
      {factorSet === "europe" ? (
        <p className="side-note fs-note">
          Factors: <b>Developed Europe</b>, five factors plus momentum. Macro, energy and world beta keep their US inputs.
        </p>
      ) : null}
    </>
  );
}
