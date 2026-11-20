import { fill } from "../report/StepCard";

export interface RunButtonProps {
  /** A run is on its way: the button reads "Factoring…", keeps focus and ignores presses. */
  busy?: boolean;
  /** Fill of the line along the bottom edge, 0 to 1 (done steps over all steps). */
  progress?: number;
  label?: string;
}

/**
 * The "Factor it" button (Sprint 4 mockup 1, frame b). While a run is on its way it is
 * `aria-disabled`, not `disabled`, so focus stays on it; a press does nothing. A 3 px line along the
 * bottom edge shows how far the steps have come. No spinner.
 */
export function RunButton({ busy = false, progress = 0, label = "Factor it" }: RunButtonProps) {
  return (
    <button
      type="submit"
      className="btn"
      aria-disabled={busy ? "true" : undefined}
      onClick={(event) => {
        if (busy) event.preventDefault();
      }}
    >
      <span>{busy ? "Factoring…" : label}</span>
      {busy ? (
        <span className="btn-prog" aria-hidden="true" style={fill(progress)}>
          <i />
        </span>
      ) : null}
    </button>
  );
}
