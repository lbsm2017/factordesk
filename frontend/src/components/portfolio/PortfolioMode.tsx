/**
 * The portfolio mode (`m=portfolio`): saved portfolios in the sidebar, the composer in the main
 * area, and after a run the composer folded into one line with the report below it. The library
 * comes from the API; the saved portfolios live in this browser only.
 */
import { useEffect, useRef, useState } from "react";
import { toApiError, useLibrary, usePortfolioReport } from "../../api/queries";
import { expectedPlan, PORTFOLIO_RUN, runView, useRunProgress } from "../../api/runProgress";
import type { FactorReport } from "../../api/types";
import type { PortfolioRunInput } from "../../api/queries";
import { lineCount } from "../../portfolio/composer";
import { buildPreset, presetById } from "../../portfolio/presets";
import type { PresetId } from "../../portfolio/presets";
import { reportCurrency } from "../../api/currency";
import { remainder, totalWeight } from "../../portfolio/tree";
import type { PortfolioTree } from "../../portfolio/tree";
import { usePortfolioStore } from "../../portfolio/usePortfolioStore";
import type { Currency } from "../../state/currency";
import { runAnnouncement, useClearFinishedRun, useReveal, useRunVisible } from "../../state/runUi";
import type { UrlState } from "../../state/url";
import { StatsSwitch } from "../controls/StatsSwitch";
import { ModeSwitch } from "../controls/ModeSwitch";
import { PlaceholderPage } from "../report/PlaceholderPage";
import { RerunBanner } from "../report/RerunBanner";
import { RerunBar } from "../report/RerunBar";
import { ReportView } from "../report/ReportView";
import { RunAnnouncer } from "../report/RunAnnouncer";
import { Shell } from "../shell/Shell";
import { Icon } from "../shell/icons";
import "../../styles/portfolio.css";
import { BacktestCard } from "./BacktestCard";
import { Composer } from "./Composer";
import { PortfolioSidebar } from "./PortfolioSidebar";
import { UndoToast } from "./UndoToast";

export interface PortfolioModeProps {
  state: UrlState;
  /** The effective reference currency (URL, stored choice or USD) and its setter. */
  currency: Currency;
  onCurrency: (currency: Currency) => void;
  onCommit: (patch: Partial<UrlState>) => void;
}

function lines(n: number): string {
  return `${n} ${n === 1 ? "line" : "lines"}`;
}

/** "97% + 3% USD cash" or "100% allocated", for the folded summary. */
function allocationText(tree: PortfolioTree, currency: Currency): string {
  const rest = remainder(tree);
  const invested = totalWeight(tree);
  const fmt = (x: number) => `${Number((x * 100).toFixed(1))}%`;
  return rest > 0 ? `${fmt(invested)} + ${fmt(rest)} ${currency} cash` : `${fmt(invested)} allocated`;
}

export function PortfolioMode({ state, currency, onCurrency, onCommit }: PortfolioModeProps) {
  const store = usePortfolioStore();
  const library = useLibrary();
  const run = usePortfolioReport();
  const { active } = store;
  /** The portfolio whose report is on screen, with the tree that was run and its report. */
  const [ran, setRan] = useState<{ id: string; tree: PortfolioTree; report: FactorReport } | null>(null);
  const [dismissed, setDismissed] = useState<number | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const foldRef = useRef<HTMLDivElement>(null);
  const libraryLines = library.data?.lines ?? [];

  const folded = ran !== null && active !== null && ran.id === active.id;
  const report = folded ? ran.report : undefined;
  const pending = run.isPending;
  const rerun = pending && folded;

  // The steps of the run, the page that shows them and the reveal of the report that arrives.
  const progress = useRunProgress(PORTFOLIO_RUN);
  const view = runView(progress, expectedPlan({ prices: true, fx: currency === "EUR" }));
  const visible = useRunVisible(pending, progress);
  const reveal = useReveal(run.data, pending, visible);
  useClearFinishedRun(PORTFOLIO_RUN, run.isSuccess);

  const input = (tree: PortfolioTree): PortfolioRunInput => ({
    tree,
    model: state.model,
    currency,
    range: state.range,
    start: state.start,
    end: state.end,
  });

  const execute = (id: string, tree: PortfolioTree) => {
    run.mutate(input(tree), { onSuccess: (data) => setRan({ id, tree, report: data }) });
  };

  const start = () => {
    if (active === null) return;
    execute(active.id, active.tree);
  };

  // A model or currency change re-runs the report on screen (the result is not cached).
  const lastModel = useRef(state.model);
  const lastCurrency = useRef(currency);
  useEffect(() => {
    if (lastModel.current === state.model && lastCurrency.current === currency) return;
    lastModel.current = state.model;
    lastCurrency.current = currency;
    if (ran !== null && !run.isPending) execute(ran.id, ran.tree);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.model, currency]);

  // Focus follows the view: the summary after a run, the heading after Edit.
  const wasFolded = useRef(false);
  useEffect(() => {
    if (folded && !wasFolded.current) foldRef.current?.focus();
    wasFolded.current = folded;
  }, [folded]);

  const select = (id: string) => {
    store.select(id);
    run.reset();
    setRan(null);
  };

  const create = (preset: PresetId, name: string) => {
    const label = name.trim() === "" ? presetById(preset).label : name.trim();
    store.create(buildPreset(preset, label, libraryLines));
    run.reset();
    setRan(null);
  };

  const importTree = (tree: PortfolioTree) => {
    store.create(tree);
    run.reset();
    setRan(null);
  };

  const sidebarStore = { ...store, select };
  const error = run.isError && !folded ? toApiError(run.error) : null;
  const rerunError = run.isError && folded ? toApiError(run.error) : null;

  const sidebar = (
    <>
      <ModeSwitch mode={state.mode} onSelect={(mode) => onCommit({ mode })} currency={currency} onCurrency={onCurrency} />
      <PortfolioSidebar
        store={sidebarStore}
        ready={library.isSuccess}
        onCreate={create}
        library={libraryLines}
        onImport={importTree}
      />
      <StatsSwitch />
    </>
  );

  let main;
  if (pending && visible && !folded && active !== null) {
    main = <PlaceholderPage mode="portfolio" title={active.tree.name} view={view} />;
  } else if (active === null) {
    main = (
      <main className="pf-landing" data-testid="portfolio-landing" id="main">
        <h1>
          <span className="ticker">Portfolio</span>
        </h1>
        <p className="coverage">
          Build a portfolio from the Asset Class Library, set the weights, then run a monthly-rebalanced backtest and read
          its factor report. Portfolios are saved in this browser only. Start from a preset:
        </p>
        <div className="row">
          {(["blank", "6040", "saa", "growth"] as const).map((id) => (
            <button
              key={id}
              type="button"
              className="btn-outline"
              disabled={!library.isSuccess}
              onClick={() => create(id, "")}
            >
              {presetById(id).label}
            </button>
          ))}
        </div>
        {library.isError ? (
          <p className="coverage" role="alert">
            {toApiError(library.error).message} {toApiError(library.error).action}
          </p>
        ) : null}
      </main>
    );
  } else if (folded && report !== undefined && ran !== null) {
    main = (
      <>
        <div className="pf-fold-wrap">
          <div ref={foldRef} className="fold" role="group" aria-label="Portfolio summary" tabIndex={-1}>
            <div>
              <Icon name="check" className="icon ok-icon" />
              <span className="fname-b">{ran.tree.name}</span>
            </div>
            <div>
              <span>{lines(lineCount(ran.tree))}</span>
            </div>
            <div>
              <span>{allocationText(ran.tree, reportCurrency(report))}</span>
            </div>
            <div>
              <span className="dim">Monthly, {ran.tree.cost_bps} bps</span>
            </div>
            <div className="go">
              <button
                type="button"
                className="btn-outline"
                onClick={() => {
                  setRan(null);
                  window.setTimeout(() => headingRef.current?.focus(), 0);
                }}
              >
                <Icon name="edit" />
                Edit
              </button>
            </div>
          </div>
          {report.portfolio_backtest ? (
            <BacktestCard section={report.portfolio_backtest} currency={reportCurrency(report)} />
          ) : null}
        </div>
        {rerun && visible ? <RerunBar title={ran.tree.name} view={view} /> : null}
        {rerunError !== null && dismissed !== run.submittedAt ? (
          <RerunBanner
            error={rerunError}
            previous={ran.tree.name}
            onRetry={() => execute(ran.id, ran.tree)}
            onDismiss={() => setDismissed(run.submittedAt)}
          />
        ) : null}
        <ReportView
          report={report}
          downloadHref={null}
          win={state.win}
          onWinChange={(win) => onCommit({ win })}
          busy={rerun}
          dim={rerun && visible}
          reveal={reveal}
        />
      </>
    );
  } else {
    main = (
      <main className="pf-pad" id="main" data-testid="composer">
        <header className="masthead edit-head">
          <div className="page-head">
            <h1>
              <span className="ticker">{active.tree.name}</span>
              <span className="nm">Portfolio</span>
            </h1>
            <span className="badge">Backtest</span>
            <span className="listing">
              Choose sub-asset classes from the library, set the weights, then run a monthly-rebalanced backtest. Saved in this
              browser.
            </span>
          </div>
        </header>
        {library.isError ? (
          <div className="pf-error" role="alert">
            <svg className="glyph" viewBox="0 0 16 16" aria-hidden="true">
              <rect x="3" y="3" width="10" height="10" />
            </svg>
            <div>
              <b>{toApiError(library.error).message}</b>
              <span className="do">{toApiError(library.error).action}</span>
            </div>
          </div>
        ) : library.isPending ? (
          <p className="coverage" role="status">
            Loading the library.
          </p>
        ) : (
          <Composer
            tree={active.tree}
            library={libraryLines}
            currency={currency}
            running={run.isPending}
            error={error}
            onChange={(tree) => store.edit(active.id, tree)}
            onRun={start}
            headingRef={headingRef}
          />
        )}
      </main>
    );
  }

  return (
    <>
      <Shell sidebar={sidebar} report={report} ticker={active?.tree.name ?? null} currency={currency}>
        <RunAnnouncer text={runAnnouncement(pending, progress, run.data !== undefined ? run.data.ticker : null)} />
        {main}
      </Shell>
      <UndoToast deleted={store.state.deleted} onUndo={store.undo} onDismiss={store.dismissUndo} />
    </>
  );
}
