import "../../styles/frame.css";

/** Panel titles and the class that `frame.css` gives a fixed height (one set for every width). */
const FRAMES = [
  ["summary", "Summary"],
  ["price", "Price"],
  ["exposures", "Factor exposures"],
  ["returns", "Return sources"],
  ["risk", "Risk sources"],
  ["rolling", "Exposure over time"],
  ["data", "Data and audit"],
  ["regression", "Regression detail"],
] as const;

const BAR = ["Analysis period", "Observations", "Factor data", "Benchmark"] as const;

/**
 * First load (dashboard spec DB6.4): the page frame with placeholders, inside the same shell as the
 * report, so the sidebar stays put. The header and the analysis bar keep their real size; each panel
 * holds one fixed height from `frame.css` (no measured width tiers). No spinner.
 */
export function LoadingFrame({ ticker }: { ticker: string }) {
  return (
    <main className="report-region" aria-busy="true" data-testid="loading-frame">
      <p className="vh" role="status">
        {`Loading the report for ${ticker}.`}
      </p>
      <header className="masthead sk-head">
        <div className="page-head">
          <h1>
            <span className="ticker">{ticker}</span>
          </h1>
        </div>
        <dl className="abar" aria-hidden="true">
          {BAR.map((label) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>0 Aug 0000</dd>
            </div>
          ))}
        </dl>
      </header>
      {FRAMES.map(([key, title]) => (
        <section key={key} className={`panel sk-panel sk-${key}`} aria-hidden="true">
          <div className="panel-head">
            <h2>{title}</h2>
          </div>
          <div className="sk-body" />
        </section>
      ))}
    </main>
  );
}
