import { useId, useState } from "react";
import { formatPercent, parsePercent } from "../../portfolio/composer";

export interface WeightInputProps {
  /** The weight as a decimal fraction. */
  value: number;
  /** What the field is for, for assistive technology ("Weight of Gold"). */
  label: string;
  onChange: (weight: number) => void;
  /** Arrow up and down: +1 and -1 steps of 0.5 points. */
  onNudge: (steps: number) => void;
}

/**
 * A typed percent field with the % sign beside it. While the user types, the text is theirs and a
 * valid number is passed up at once, so the live panel follows; when the field loses focus it shows
 * the stored weight again. Arrow keys nudge the weight by 0.5 points. A value that is not a number
 * from 0 to 100 is marked and said in words.
 */
export function WeightInput({ value, label, onChange, onNudge }: WeightInputProps) {
  const [draft, setDraft] = useState<string | null>(null);
  const errorId = useId();
  const invalid = draft !== null && parsePercent(draft) === null;
  const shown = draft ?? formatPercent(value);
  const zero = draft === null && value === 0;
  return (
    <>
      <span className={zero ? "w zero" : "w"}>
        <input
          type="text"
          inputMode="decimal"
          autoComplete="off"
          aria-label={label}
          aria-invalid={invalid}
          {...(invalid ? { "aria-describedby": errorId } : {})}
          value={shown}
          onFocus={(event) => event.currentTarget.select()}
          onChange={(event) => {
            const text = event.target.value;
            setDraft(text);
            const parsed = parsePercent(text);
            if (parsed !== null) onChange(parsed);
          }}
          onBlur={() => setDraft(null)}
          onKeyDown={(event) => {
            if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
            event.preventDefault();
            setDraft(null);
            onNudge(event.key === "ArrowUp" ? 1 : -1);
          }}
        />
        <span className="u" aria-hidden="true">
          %
        </span>
      </span>
      {invalid ? (
        <span className="werr" id={errorId} role="alert">
          Use 0 to 100
        </span>
      ) : null}
    </>
  );
}
