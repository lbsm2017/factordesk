import { useEffect, useRef } from "react";
import { runView } from "../../api/runProgress";
import type { RunProgress } from "../../api/runProgress";
import type { ApiError, ProgressStepId } from "../../api/types";
import { StepCard } from "./StepCard";
import "../../styles/frame.css";

export interface ErrorFrameProps {
  ticker: string;
  error: ApiError;
  /** The steps the failed run reached; without any, the page has no step card. */
  progress?: RunProgress;
  /** The steps the run was expected to have (names of the steps that did not start). */
  plan?: readonly ProgressStepId[];
  /** Runs the same request again. */
  onRetry?: () => void;
  /** Moves focus to the field the user changes (the ticker field). */
  onChange?: () => void;
  changeLabel?: string;
}

/**
 * First-run error (Sprint 4 mockup 1, frame f): the page heading, the notice (what happened, then
 * what to do), the buttons, then the step card with the step that stopped. Focus moves to the
 * notice when it appears.
 */
export function ErrorFrame({ ticker, error, progress, plan = [], onRetry, onChange, changeLabel = "Change ticker" }: ErrorFrameProps) {
  const notice = useRef<HTMLDivElement>(null);
  useEffect(() => {
    notice.current?.focus();
  }, []);
  const view = progress !== undefined && progress.steps.length > 0 ? runView(progress, plan, true) : null;
  return (
    <main className="report-region req-error" data-testid="report-error">
      <header className="masthead">
        <h1>
          <span className="ticker" translate="no">
            {ticker}
          </span>
        </h1>
      </header>
      <div className="notice" role="alert" tabIndex={-1} ref={notice}>
        <svg className="glyph glyph-square" viewBox="0 0 16 16" aria-hidden="true">
          <rect x="3" y="3" width="10" height="10" />
        </svg>
        <div>
          <p className="notice-sum">
            <span className="vh">Error: </span>
            {error.message}
          </p>
          <p className="notice-do">{error.action}</p>
          {onRetry !== undefined || onChange !== undefined ? (
            <div className="err-actions">
              {onRetry !== undefined ? (
                <button type="button" className="btn on-light" onClick={onRetry}>
                  Try again
                </button>
              ) : null}
              {onChange !== undefined ? (
                <button type="button" className="btn-outline" onClick={onChange}>
                  {changeLabel}
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
      {view !== null && view.rows.length > 0 ? <StepCard title={ticker} view={view} status="failed" /> : null}
    </main>
  );
}
