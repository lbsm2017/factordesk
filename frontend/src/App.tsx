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
import { ControlsStrip } from "./components/controls/ControlsStrip";
import { ModeSwitch } from "./components/controls/ModeSwitch";
import { ModelToggle } from "./components/controls/ModelToggle";
import { Landing, TrackLanding } from "./components/controls/ReportStates";
import { TrackRecordInput } from "./components/controls/TrackRecordInput";
import { ErrorFrame } from "./components/report/ErrorFrame";
import { LoadingFrame } from "./components/report/LoadingFrame";
import { ReportView } from "./components/report/ReportView";
import { Shell } from "./components/shell/Shell";
import { addRecent, useRecent } from "./state/recent";
import type { RollingWindowDays } from "./state/url";
import { StatsProvider, useStatsSwitch } from "./state/stats";
import { useUrlState } from "./state/useUrlState";
import "./styles/controls.css";
import { Switch } from "./ui/Switch";

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

/** "Show statistics" in the sidebar (design K.1), stored in the URL as `stats=1`. */
function StatsSwitch() {
  const [on, setOn] = useStatsSwitch();
  return (
    <div className="side-group">
      <Switch label="Show statistics" hint="t, p-values, intervals" checked={on} onChange={setOn} />
    </div>
  );
}

const TRACK_TITLE = "Track record";

function Dashboard() {
  const [state, commit] = useUrlState();
  const [query, setQuery] = useState("");
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const recent = useRecent();
  const factors = useFactorStatus();
  const suggestions = useTickerSuggestions(query);
  // In the track-record mode no ticker is requested, whatever `t` says.
  const track = state.mode === "track";
  const tickerState = track ? { ...state, ticker: null } : state;
  const ranges = useRanges(tickerState.ticker);
  const report = useReport(tickerState);
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

  // A model change re-runs the record on screen with the new model (the upload result is not cached).
  const lastModel = useRef(state.model);
  useEffect(() => {
    if (lastModel.current === state.model) return;
    lastModel.current = state.model;
    if (track && upload.variables !== undefined && !upload.isPending) {
      upload.mutate({ ...upload.variables, model: state.model });
    }
  }, [state.model, track, upload]);

  const loadedTicker = !track && report.isSuccess && !report.isPlaceholderData ? report.data.ticker : null;
  useEffect(() => {
    if (loadedTicker !== null) addRecent(loadedTicker);
  }, [loadedTicker]);

  return (
    <Shell
      report={shown}
      ticker={track ? (shown?.ticker ?? null) : state.ticker}
      sidebar={
        <>
          <ModeSwitch mode={state.mode} onSelect={(mode) => commit({ mode })} />
          {track ? (
            <TrackRecordInput busy={upload.isPending} onRun={(input) => upload.mutate({ ...input, model: state.model })} />
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
          <div className="side-group">
            <ModelToggle selected={state.model} onSelect={(model) => commit({ model })} />
          </div>
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
          downloadHref={downloadHref(state)}
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
