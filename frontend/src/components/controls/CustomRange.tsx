import { useId, useState } from "react";
import type { KeyboardEvent } from "react";
import { dateLong, isIsoDate } from "../../format";

export interface CustomRangeProps {
  /** ISO dates, or "" when empty. Chip choices fill these with the analysed dates. */
  start: string;
  end: string;
  /** Last factor date (the `max` of both date fields), or null while unknown. */
  max: string | null;
  /** Called when a complete, valid pair is entered and the user leaves the field or presses Enter. */
  onCommit: (start: string, end: string) => void;
  /** No ticker is loaded yet, so the dates have no effect. */
  disabled?: boolean;
}

/** The earliest date that can be chosen: no factor or price series starts before this. */
export const MIN_DATE = "1970-01-01";

/** A sentence for a pair that must not be sent, or null when the pair is fine. */
function problem(start: string, end: string, max: string | null): string | null {
  for (const date of [start, end]) {
    if (!isIsoDate(date)) return "Enter a complete date with day, month and year, for example 8 Aug 2024.";
  }
  if (start > end) {
    return `The start date ${dateLong(start)} is after the end date ${dateLong(end)}. Choose a start date before the end date.`;
  }
  for (const date of [start, end]) {
    if (date < MIN_DATE) {
      return `${dateLong(date)} is too early. Dates before ${dateLong(MIN_DATE)} cannot be chosen. Choose a later date.`;
    }
    if (max !== null && date > max) {
      return `Factor data ends ${dateLong(max)}, so ${dateLong(date)} cannot be chosen. Choose an earlier date.`;
    }
  }
  return null;
}

/**
 * From and To (dashboard spec DB6.3). Typing only edits a draft: the pair is checked and committed
 * when a field loses focus or Enter is pressed, never on partial input (a typed year passes through
 * 0002, 0020 and 0202 on its way to 2023). An invalid pair shows a sentence and sends nothing; an
 * unchanged pair does nothing.
 */
export function CustomRange({ start, end, max, onCommit, disabled = false }: CustomRangeProps) {
  const [draft, setDraft] = useState({ start, end });
  const [seen, setSeen] = useState({ start, end });
  const [message, setMessage] = useState<string | null>(null);
  if (seen.start !== start || seen.end !== end) {
    setSeen({ start, end });
    setDraft({ start, end });
    setMessage(null);
  }
  const errorId = useId();

  const edit = (next: { start: string; end: string }) => {
    setDraft(next);
    setMessage(null);
  };

  const commit = () => {
    if (draft.start === start && draft.end === end) {
      setMessage(null);
      return;
    }
    const found = problem(draft.start, draft.end, max);
    setMessage(found);
    if (found === null) onCommit(draft.start, draft.end);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    }
  };

  const described = message !== null ? { "aria-describedby": errorId } : {};
  const limit = { min: MIN_DATE, ...(max !== null ? { max } : {}) };
  return (
    <div className="ctl-custom-wrap">
      <div className="ctl-custom" role="group" aria-label="Custom dates">
        <label>
          From{" "}
          <input
            type="date"
            value={draft.start}
            {...limit}
            disabled={disabled}
            aria-invalid={message !== null}
            {...described}
            onChange={(event) => edit({ start: event.target.value, end: draft.end })}
            onBlur={commit}
            onKeyDown={onKeyDown}
          />
        </label>
        <label>
          To{" "}
          <input
            type="date"
            value={draft.end}
            {...limit}
            disabled={disabled}
            aria-invalid={message !== null}
            {...described}
            onChange={(event) => edit({ start: draft.start, end: event.target.value })}
            onBlur={commit}
            onKeyDown={onKeyDown}
          />
        </label>
      </div>
      {message !== null ? (
        <p className="ctl-err" id={errorId} role="alert">
          {message}
        </p>
      ) : null}
    </div>
  );
}
