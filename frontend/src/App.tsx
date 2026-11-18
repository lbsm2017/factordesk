/**
 * Page shell: URL state, the controls strip, the data flow and the states between them
 * (dashboard spec DB6). The 1216 px column is the `.report` class (design C).
 */
import { useEffect, useState } from "react";
import {
  downloadHref,
  toApiError,
  useFactorStatus,
  useRanges,
  useRefreshFactors,
  useReport,
  useTickerSuggestions,
} from "./api/queries";
import type { FactorReport } from "./api/types";
import { ControlsStrip } from "./components/controls/ControlsStrip";
import { ErrorNotice, Landing, LoadingFrame } from "./components/controls/ReportStates";
import { ReportView } from "./components/report/ReportView";
import { addRecent, useRecent } from "./state/recent";
import type { RollingWindowDays } from "./state/url";
import { useUrlState } from "./state/useUrlState";
import "./styles/controls.css";

/** Development only: `/?demo=1` renders the mock report so the panels can be seen without the API. */
function demoRequested(): boolean {
  return new URLSearchParams(window.location.search).get("demo") === "1";
}

function DemoPage() {
  const [report, setReport] = useState<FactorReport | null>(null);
  const [win, setWin] = useState<RollingWindowDays | null>(null);
  useEffect(() => {
    void import("./test/fixture").then((m) => setReport(m.mockReport));
  }, []);
  return (
    <div className="report">
      {report ? <ReportView report={report} downloadHref="#" win={win} onWinChange={setWin} /> : null}
    </div>
  );
}

function Dashboard() {
  const [state, commit] = useUrlState();
  const [query, setQuery] = useState("");
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const recent = useRecent();
  const factors = useFactorStatus();
  const suggestions = useTickerSuggestions(query);
  const ranges = useRanges(state.ticker);
  const report = useReport(state);
  const refresh = useRefreshFactors(setRefreshMessage);

  // A stale report is never shown under an error, and never on the landing page.
  const shown = state.ticker === null || report.isError ? undefined : report.data;
  const busy = state.ticker !== null && report.isFetching && shown !== undefined;

  const loadedTicker = report.isSuccess && !report.isPlaceholderData ? report.data.ticker : null;
  useEffect(() => {
    if (loadedTicker !== null) addRecent(loadedTicker);
  }, [loadedTicker]);

  return (
    <div className="report">
      <ControlsStrip
        state={state}
        recent={recent}
        suggestions={suggestions.data?.items ?? []}
        ranges={state.ticker === null ? undefined : ranges.data}
        factorStatus={factors.data}
        report={shown}
        busy={busy}
        refreshing={refresh.isPending}
        refreshMessage={refreshMessage}
        onQueryChange={setQuery}
        onCommit={commit}
        onRefreshFactors={() => {
          setRefreshMessage(null);
          refresh.mutate();
        }}
      />
      {state.ticker === null ? (
        <Landing recent={recent} onPick={(ticker) => commit({ ticker })} />
      ) : report.isError ? (
        <ErrorNotice error={toApiError(report.error)} />
      ) : shown === undefined ? (
        <LoadingFrame ticker={state.ticker} />
      ) : (
        <ReportView
          report={shown}
          downloadHref={downloadHref(state)}
          win={state.win}
          onWinChange={(win) => commit({ win })}
          busy={busy}
        />
      )}
    </div>
  );
}

export function App() {
  return import.meta.env.DEV && demoRequested() ? <DemoPage /> : <Dashboard />;
}
