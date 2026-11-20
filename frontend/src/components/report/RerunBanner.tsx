import type { ApiError } from "../../api/types";
import "../../styles/frame.css";

export interface RerunBannerProps {
  error: ApiError;
  /** The ticker (or name) of the report that stays on screen. */
  previous: string;
  onRetry: () => void;
  onDismiss: () => void;
}

/**
 * A re-run failed while a report was on screen (Sprint 4 mockup 1, frame f): the old report stays at
 * full strength under this banner, which says it is the previous one and for which ticker.
 */
export function RerunBanner({ error, previous, onRetry, onDismiss }: RerunBannerProps) {
  return (
    <div className="err-banner" role="alert" data-testid="rerun-error">
      <svg className="glyph glyph-square" viewBox="0 0 16 16" aria-hidden="true">
        <rect x="3" y="3" width="10" height="10" />
      </svg>
      <div>
        <p className="notice-sum">
          <span className="vh">Error: </span>
          {error.message} {error.action} The report below is the previous one, for {previous}.
        </p>
        <div className="err-actions">
          <button type="button" className="btn on-light" onClick={onRetry}>
            Try again
          </button>
          <button type="button" className="dismiss" onClick={onDismiss}>
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
