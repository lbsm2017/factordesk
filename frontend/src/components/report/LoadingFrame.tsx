import "../../styles/frame.css";

const KPI_LABELS = [
  ["Alpha, a year", "Distinguishable from zero at 5%"],
  ["R²", "Share of daily variance the factors explain"],
  ["Residual volatility", "A year, left unexplained by the factors"],
  ["Observations", "Trading days; none excluded"],
  ["Analysed range", "Requested 1 Jan 2020 to 30 Sep 2026"],
] as const;

/** Panel titles and the id that `frame.css` sizes them by (final heights, three width tiers). */
const FRAMES = [
  ["price", "Price"],
  ["exposures", "Factor exposures"],
  ["returns", "Where the return came from"],
  ["risk", "Where the risk comes from"],
  ["rolling", "Exposure over time"],
  ["data", "Data and audit"],
  ["regression", "Regression detail"],
] as const;

/**
 * First load (dashboard spec DB6.4): the page frame at final heights, with placeholders for the
 * ticker, the equation and the KPI cells and `--sunk` panel bodies. No spinner. The heights come
 * from the rendered panels (see `frame.css`), so the report arrives without layout shift.
 */
export function LoadingFrame({ ticker }: { ticker: string }) {
  return (
    <main className="report-region" aria-busy="true" data-testid="loading-frame">
      <p className="vh" role="status">
        {`Loading the report for ${ticker}.`}
      </p>
      <div aria-hidden="true">
        <header className="masthead sk-head">
          <div className="mast-top">
            <h1>
              <span className="ticker">{ticker}</span>
              <span className="what">Fama–French five-factor profile</span>
            </h1>
            <p className="mast-meta">
              <span className="chip sk-chip" />
              <span className="btn-secondary sk-chip" />
            </p>
          </div>
        </header>
        <div className="sk-notice" />
        <div className="model sk-eq" />
        <div className="kpis sk-kpis">
          <dl>
            {KPI_LABELS.map(([label, note]) => (
              <div key={label} className="kpi">
                <dt>{label}</dt>
                <dd className="v">0.000</dd>
                <dd className="n">{note}</dd>
              </div>
            ))}
          </dl>
        </div>
        {FRAMES.map(([key, title]) => (
          <section key={key} className={`panel sk-panel sk-${key}`}>
            <div className="panel-head">
              <div>
                <h2>{title}</h2>
              </div>
            </div>
            <div className="sk-body" />
          </section>
        ))}
        <div className="colophon sk-colophon" />
      </div>
    </main>
  );
}
