import type { ApiError } from "../../api/types";
import "../../styles/frame.css";

/**
 * Request error: the page heading (the ticker, so the page always has one h1), then the notice
 * style (square glyph, what went wrong, then what to do). Replaces the report; a stale report is
 * never shown under an error.
 */
export function ErrorFrame({ ticker, error }: { ticker: string; error: ApiError }) {
  return (
    <main className="report-region req-error" data-testid="report-error">
      <header className="masthead">
        <h1>
          <span className="ticker">{ticker}</span>
        </h1>
      </header>
      <div className="notice" role="alert">
        <svg className="glyph glyph-square" viewBox="0 0 16 16" aria-hidden="true">
          <rect x="3" y="3" width="10" height="10" />
        </svg>
        <div>
          <p className="notice-sum">
            <span className="vh">Error: </span>
            {error.message}
          </p>
          <p className="notice-do">{error.action}</p>
        </div>
      </div>
    </main>
  );
}
