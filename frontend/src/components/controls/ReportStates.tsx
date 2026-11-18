import type { ApiError } from "../../api/types";

/** Landing: no ticker in the URL (dashboard spec DB6.4). The strip above holds the focused search field. */
export function Landing({ recent, onPick }: { recent: string[]; onPick: (ticker: string) => void }) {
  return (
    <main className="landing" data-testid="landing">
      <h1>
        <span className="ticker">factordesk</span>
      </h1>
      <p className="coverage">Type a ticker and press Factor it, for example SPY.</p>
      {recent.length > 0 ? (
        <p className="landing-recent">
          <span>Recent tickers</span>
          {recent.map((ticker) => (
            <button key={ticker} type="button" className="chip" onClick={() => onPick(ticker)}>
              {ticker}
            </button>
          ))}
        </p>
      ) : null}
    </main>
  );
}

const KPI_LABELS = ["Alpha a year", "R²", "Residual volatility", "Observations", "Analysed range"] as const;

const FRAMES: readonly (readonly [string, number])[] = [
  ["Price", 360],
  ["Factor exposures", 300],
  ["Where the return came from", 300],
  ["Where the risk comes from", 300],
  ["Exposure over time", 340],
  ["Data and audit", 260],
  ["Regression detail", 300],
];

/**
 * First load (dashboard spec DB6.4): the page frame at final heights with `--grid` placeholders
 * (the `[aria-busy="true"]` rule paints the ticker and the KPI values) and `--sunk` panel bodies.
 * No spinner, no layout shift when the report arrives.
 */
export function LoadingFrame({ ticker }: { ticker: string }) {
  return (
    <main className="report-region" aria-busy="true" data-testid="loading-frame">
      <p className="vh" role="status">
        {`Loading the report for ${ticker}.`}
      </p>
      <div aria-hidden="true">
        <header>
          <h1>
            <span className="ticker">{ticker}</span>
          </h1>
        </header>
        <div className="skel-eq" />
        <div className="kpis">
          <dl>
            {KPI_LABELS.map((label) => (
              <div key={label} className="kpi">
                <dt>{label}</dt>
                <dd className="v">0.000</dd>
              </div>
            ))}
          </dl>
        </div>
        {FRAMES.map(([title, height]) => (
          <section key={title} className="panel">
            <div className="panel-head">
              <div>
                <h2>{title}</h2>
              </div>
            </div>
            <div className="skel-body" style={{ height }} />
          </section>
        ))}
      </div>
    </main>
  );
}

/** Request error: the notice style (square glyph, what went wrong, then what to do). Replaces the report. */
export function ErrorNotice({ error }: { error: ApiError }) {
  return (
    <main className="report-region req-error" data-testid="report-error">
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
