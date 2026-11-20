/**
 * Page: URL state, the shell with the controls in the sidebar, the data flow and the states between
 * them (dashboard spec DB6, prototype v4a). The "Show statistics" switch lives in `StatsProvider`.
 */
import { useEffect, useRef, useState } from "react";
import {
  downloadHref,
  toApiError,
  useFactorStatus,
  useRanges,
  useRefreshFactors,
  useReport,
  useTickerSuggestions,
  useUploadReport,
} from "./api/queries";
import type { FactorReport } from "./api/types";
import { AnalysedRange } from "./components/controls/AnalysedRange";
import { ControlsStrip } from "./components/controls/ControlsStrip";
import { ModeSwitch } from "./components/controls/ModeSwitch";
import { StatsSwitch } from "./components/controls/StatsSwitch";
import { Landing, TrackLanding } from "./components/controls/ReportStates";
import { TrackRecordInput } from "./components/controls/TrackRecordInput";
import { PortfolioMode } from "./components/portfolio/PortfolioMode";
import { ErrorFrame } from "./components/report/ErrorFrame";
import { LoadingFrame } from "./components/report/LoadingFrame";
import { ReportView } from "./components/report/ReportView";
import { Shell } from "./components/shell/Shell";
import { useCurrency } from "./state/currency";
import { addRecent, useRecent } from "./state/recent";
import type { RollingWindowDays } from "./state/url";
import { StatsProvider } from "./state/stats";
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
    <Shell sidebar={<StatsSwitch />} report={report ?? undefined} ticker={report?.ticker ?? null}>
      {report ? <ReportView report={report} downloadHref="#" win={win} onWinChange={setWin} /> : null}
    </Shell>
  );
}

const TRACK_TITLE = "Track record";

function Dashboard() {
  const [state, commit] = useUrlState();
  const [currency, setCurrency] = useCurrency(state.ccy, commit);
  const [query, setQuery] = useState("");
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const recent = useRecent();
  const factors = useFactorStatus();
  const suggestions = useTickerSuggestions(query);
  // In the track-record and portfolio modes no ticker is requested, whatever `t` says.
  const track = state.mode === "track";
  const portfolio = state.mode === "portfolio";
  const tickerState = track || portfolio ? { ...state, ticker: null } : state;
  const ranges = useRanges(tickerState.ticker, currency);
  const report = useReport(tickerState, currency);
  const refresh = useRefreshFactors(setRefreshMessage);
  const upload = useUploadReport();

  // A stale report is never shown under an error, and never on the landing page.
  const shown = track
    ? upload.isSuccess
      ? upload.data
      : undefined
    : state.ticker === null || report.isError
      ? undefined
      : report.data;
  const busy = !track && state.ticker !== null && report.isFetching && shown !== undefined;

  // A model or currency change re-runs the record on screen (the upload result is not cached).
  const lastModel = useRef(state.model);
  const lastCurrency = useRef(currency);
  useEffect(() => {
    if (lastModel.current === state.model && lastCurrency.current === currency) return;
    lastModel.current = state.model;
    lastCurrency.current = currency;
    if (track && upload.variables !== undefined && !upload.isPending) {
      upload.mutate({ ...upload.variables, model: state.model, ccy: currency });
    }
  }, [state.model, currency, track, upload]);

  const loadedTicker = !track && report.isSuccess && !report.isPlaceholderData ? report.data.ticker : null;
  useEffect(() => {
    if (loadedTicker !== null) addRecent(loadedTicker);
  }, [loadedTicker]);

  if (portfolio) return <PortfolioMode state={state} currency={currency} onCurrency={setCurrency} onCommit={commit} />;

  return (
    <Shell
      report={shown}
      ticker={track ? (shown?.ticker ?? null) : state.ticker}
      currency={currency}
      sidebar={
        <>
          <ModeSwitch mode={state.mode} onSelect={(mode) => commit({ mode })} currency={currency} onCurrency={setCurrency} />
          {track ? (
            <>
              <TrackRecordInput busy={upload.isPending} onRun={(input) => upload.mutate({ ...input, model: state.model, ccy: currency })} />
              {shown !== undefined ? (
                <div className="side-group">
                  <AnalysedRange report={shown} label="Analysed period" />
                </div>
              ) : null}
            </>
          ) : (
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
          )}
          <StatsSwitch />
        </>
      }
    >
      {track ? (
        upload.isPending ? (
          <LoadingFrame ticker={upload.variables?.name.trim() || TRACK_TITLE} />
        ) : upload.isError ? (
          <ErrorFrame ticker={upload.variables?.name.trim() || TRACK_TITLE} error={toApiError(upload.error)} />
        ) : shown === undefined ? (
          <TrackLanding />
        ) : (
          <ReportView report={shown} downloadHref={null} win={state.win} onWinChange={(win) => commit({ win })} />
        )
      ) : state.ticker === null ? (
        <Landing recent={recent} onPick={(ticker) => commit({ ticker })} />
      ) : report.isError ? (
        <ErrorFrame ticker={state.ticker} error={toApiError(report.error)} />
      ) : shown === undefined ? (
        <LoadingFrame ticker={state.ticker} />
      ) : (
        <ReportView
          report={shown}
          downloadHref={downloadHref(state, currency)}
          win={state.win}
          onWinChange={(win) => commit({ win })}
          busy={busy}
        />
      )}
    </Shell>
  );
}

export function App() {
  return <StatsProvider>{import.meta.env.DEV && demoRequested() ? <DemoPage /> : <Dashboard />}</StatsProvider>;
}
