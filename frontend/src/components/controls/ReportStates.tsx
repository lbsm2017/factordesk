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

/** Landing of the track-record mode: nothing uploaded yet. The controls are in the sidebar. */
export function TrackLanding() {
  return (
    <main className="landing" data-testid="track-landing">
      <h1>
        <span className="ticker">Track record</span>
      </h1>
      <p className="coverage">
        Drop a CSV file with a date and a return column in the sidebar and press Factor it. Each row is one calendar
        month and the return is a decimal, for example 2021-01-31,0.012. At least 36 months are needed. The file is
        analysed in memory and is not stored.
      </p>
    </main>
  );
}
