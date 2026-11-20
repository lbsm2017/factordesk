/**
 * Page: URL state, the shell with the controls in the sidebar, the data flow and the states between
 * them (dashboard spec DB6, prototype v4a). The "Show statistics" switch lives in `StatsProvider`.
 */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { barFraction, expectedPlan, runView, UPLOAD_RUN, useRunProgress } from "./api/runProgress";
import {
  downloadHref,
  reportProgressKey,
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
import { PlaceholderPage } from "./components/report/PlaceholderPage";
import { RerunBanner } from "./components/report/RerunBanner";
import { RerunBar } from "./components/report/RerunBar";
import { RunAnnouncer } from "./components/report/RunAnnouncer";
import { ReportView } from "./components/report/ReportView";
import { Shell } from "./components/shell/Shell";
import { useCurrency } from "./state/currency";
import { useFactorSetNote } from "./state/factorSetNote";
import type { FactorSet } from "./state/factorSet";
import { addRecent, useRecent } from "./state/recent";
import type { RollingWindowDays } from "./state/url";
import { runAnnouncement, useClearFinishedRun, useKept, useReveal, useRunVisible } from "./state/runUi";
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

/** Moves focus to the ticker field (the "Change ticker" button of the error page). */
function focusTicker(): void {
  document.getElementById("ticker-input")?.focus();
}

function Dashboard() {
  const [state, commit] = useUrlState();
  const [currency, setCurrency] = useCurrency(state.ccy, commit);
  const factorSet = state.fs;
  const [query, setQuery] = useState("");
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState<number | null>(null);
  const recent = useRecent();
  const factors = useFactorStatus();
  const suggestions = useTickerSuggestions(query);
  // In the track-record and portfolio modes no ticker is requested, whatever `t` says.
  const track = state.mode === "track";
  const portfolio = state.mode === "portfolio";
  const tickerState = track || portfolio ? { ...state, ticker: null } : state;
  const ranges = useRanges(tickerState.ticker, currency, factorSet);
  const report = useReport(tickerState, currency);
  const refresh = useRefreshFactors(setRefreshMessage);
  const upload = useUploadReport();

  // What is on screen: the new report, or the previous one while the next request runs or fails.
  const tickerFresh = state.ticker === null ? undefined : report.data;
  const keptTicker = useKept(tickerFresh);
  const keptTrack = useKept(upload.data);
  const fresh = track ? upload.data : tickerFresh;
  const pending = track ? upload.isPending : report.isFetching;
  const error = track ? (upload.isError ? toApiError(upload.error) : null) : report.isError ? toApiError(report.error) : null;
  const kept = track ? keptTrack : keptTicker;
  const shown = fresh ?? (pending || error !== null ? kept : undefined);
  const rerun = pending && shown !== undefined;
  // The polite sentence for a factor set change, said until the first step of the new run speaks.
  const [setNote, noteSet] = useFactorSetNote(pending);
  const chooseFactorSet = (next: FactorSet) => {
    noteSet(next);
    commit({ fs: next });
  };
  const title = track ? upload.variables?.name.trim() || TRACK_TITLE : (state.ticker ?? "");

  // The steps of the run: the expected list gives the names of the steps that have not started.
  const uploadEuro = upload.variables?.recordCurrency === "EUR" || currency === "EUR";
  const plan = expectedPlan({ prices: !track, fx: track ? uploadEuro : currency === "EUR" });
  const runKey = track ? UPLOAD_RUN : reportProgressKey(tickerState, currency);
  const progress = useRunProgress(runKey);
  const view = runView(progress, plan);
  const visible = useRunVisible(pending, progress);
  const reveal = useReveal(fresh, pending, visible);
  const readyFor = fresh !== undefined && !pending ? fresh.ticker : null;
  useClearFinishedRun(runKey, readyFor !== null && error === null);

  // A model, currency or factor set change re-runs the record on screen (the upload result is not cached).
  const lastModel = useRef(state.model);
  const lastCurrency = useRef(currency);
  const lastSet = useRef(factorSet);
  useEffect(() => {
    if (lastModel.current === state.model && lastCurrency.current === currency && lastSet.current === factorSet) return;
    lastModel.current = state.model;
    lastCurrency.current = currency;
    lastSet.current = factorSet;
    if (track && upload.variables !== undefined && !upload.isPending) {
      upload.mutate({ ...upload.variables, model: state.model, ccy: currency, factorSet });
    }
  }, [state.model, currency, factorSet, track, upload]);

  const loadedTicker = !track && report.isSuccess && !report.isPlaceholderData ? report.data.ticker : null;
  useEffect(() => {
    if (loadedTicker !== null) addRecent(loadedTicker);
  }, [loadedTicker]);

  if (portfolio) {
    return (
      <PortfolioMode
        state={state}
        currency={currency}
        onCurrency={setCurrency}
        factorSet={factorSet}
        onFactorSet={chooseFactorSet}
        onCommit={commit}
      />
    );
  }

  const stepSentence = runAnnouncement(pending, progress, readyFor);
  const announcement = stepSentence === "" && pending ? setNote : stepSentence;

  const retry = () => {
    if (track) {
      if (upload.variables !== undefined) upload.mutate(upload.variables);
    } else {
      void report.refetch();
    }
  };
  const errorStamp = track ? upload.submittedAt : report.errorUpdatedAt;
  const running = rerun && visible;

  let main: ReactNode;
  if (!track && state.ticker === null) {
    main = <Landing recent={recent} onPick={(ticker) => commit({ ticker })} />;
  } else if (error !== null && shown === undefined) {
    main = (
      <ErrorFrame
        ticker={title}
        error={error}
        progress={progress}
        plan={plan}
        onRetry={retry}
        {...(track ? {} : { onChange: focusTicker })}
      />
    );
  } else if (shown === undefined) {
    main =
      pending && visible ? (
        <PlaceholderPage mode={track ? "track" : "ticker"} title={title} view={view} />
      ) : track && !pending ? (
        <TrackLanding />
      ) : (
        <main className="report-region" aria-busy={pending} data-testid="loading-frame" />
      );
  } else {
    main = (
      <>
        {running ? <RerunBar title={title} view={view} /> : null}
        {error !== null && dismissed !== errorStamp ? (
          <RerunBanner error={error} previous={shown.ticker} onRetry={retry} onDismiss={() => setDismissed(errorStamp)} />
        ) : null}
        <ReportView
          report={shown}
          downloadHref={track || error !== null ? null : downloadHref(state, currency)}
          win={state.win}
          onWinChange={(win) => commit({ win })}
          busy={rerun}
          dim={running}
          reveal={reveal}
        />
      </>
    );
  }

  return (
    <Shell
      report={shown}
      ticker={track ? (shown?.ticker ?? null) : state.ticker}
      currency={currency}
      factorSet={factorSet}
      sidebar={
        <>
          <ModeSwitch
            mode={state.mode}
            onSelect={(mode) => commit({ mode })}
            currency={currency}
            onCurrency={setCurrency}
            factorSet={factorSet}
            onFactorSet={chooseFactorSet}
          />
          {track ? (
            <>
              <TrackRecordInput
                busy={pending}
                progress={barFraction(view)}
                onRun={(input) => upload.mutate({ ...input, model: state.model, ccy: currency, factorSet })}
              />
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
              busy={pending}
              progress={barFraction(view)}
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
      <RunAnnouncer text={announcement} />
      {main}
    </Shell>
  );
}

export function App() {
  return <StatsProvider>{import.meta.env.DEV && demoRequested() ? <DemoPage /> : <Dashboard />}</StatsProvider>;
}
