import { useId, useState } from "react";
import { dateLong, isIsoDate } from "../../format";

export interface CustomRangeProps {
  /** ISO dates, or "" when empty. Chip choices fill these with the analysed dates. */
  start: string;
  end: string;
  /** Last factor date (the `max` of both date fields), or null while unknown. */
  max: string | null;
  /** Called when a complete, valid pair is entered. */
  onCommit: (start: string, end: string) => void;
}

/** A sentence for a pair that must not be sent, or null when the pair is fine or incomplete. */
function problem(start: string, end: string, max: string | null): string | null {
  if (isIsoDate(start) && isIsoDate(end) && start > end) {
    return `The start date ${dateLong(start)} is after the end date ${dateLong(end)}. Choose a start date before the end date.`;
  }
  if (max !== null) {
    for (const date of [start, end]) {
      if (isIsoDate(date) && date > max) {
        return `Factor data ends ${dateLong(max)}, so ${dateLong(date)} cannot be chosen. Choose an earlier date.`;
      }
    }
  }
  return null;
}

/**
 * From and To (dashboard spec DB6.3). A complete, valid pair commits on change; a start after the
 * end, or a date after the factor data, shows a sentence and sends nothing.
 */
export function CustomRange({ start, end, max, onCommit }: CustomRangeProps) {
  const [draft, setDraft] = useState({ start, end });
  const [seen, setSeen] = useState({ start, end });
  if (seen.start !== start || seen.end !== end) {
    setSeen({ start, end });
    setDraft({ start, end });
  }
  const errorId = useId();

  const change = (next: { start: string; end: string }) => {
    setDraft(next);
    if (!isIsoDate(next.start) || !isIsoDate(next.end)) return;
    if (problem(next.start, next.end, max) !== null) return;
    if (next.start === start && next.end === end) return;
    onCommit(next.start, next.end);
  };

  const message = problem(draft.start, draft.end, max);
  const described = message !== null ? { "aria-describedby": errorId } : {};
  const limit = max !== null ? { max } : {};
  return (
    <div className="ctl-custom-wrap">
      <div className="ctl-custom" role="group" aria-label="Custom dates">
        <label>
          From{" "}
          <input
            type="date"
            value={draft.start}
            {...limit}
            aria-invalid={message !== null}
            {...described}
            onChange={(event) => change({ start: event.target.value, end: draft.end })}
          />
        </label>
        <label>
          To{" "}
          <input
            type="date"
            value={draft.end}
            {...limit}
            aria-invalid={message !== null}
            {...described}
            onChange={(event) => change({ start: draft.start, end: event.target.value })}
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
