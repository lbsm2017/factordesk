import type { CSSProperties } from "react";
import { useShowStats } from "../../state/stats";
import { pairClass } from "./Panel";
import { placeholderPanels } from "./placeholders";
import type { ReportMode } from "./placeholders";
import { StepCard } from "./StepCard";
import type { StepCardProps } from "./StepCard";
import "../../styles/frame.css";

const BAR = ["Analysis period", "Observations", "Factor data", "Benchmark"] as const;
const LINES = ["w1", "w2", "w1", "w3", "w2", "w1", "w4"] as const;

export interface PlaceholderPageProps extends Pick<StepCardProps, "view" | "headingRef"> {
  mode: ReportMode;
  /** The ticker, the record's name or the portfolio's name. */
  title: string;
}

/**
 * The first run's page (Sprint 4 mockup 1, frames b and c): the real header with grey facts, the run
 * card in the place of the Summary panel, then one grey placeholder per panel with its real title,
 * at its final height, in the order of the registry. Placeholders carry no id and no landmark, so the
 * section list in the sidebar stays empty until the real panels exist. No spinner, no shimmer.
 */
export function PlaceholderPage({ mode, title, view, headingRef }: PlaceholderPageProps) {
  const stats = useShowStats();
  return (
    <main className="report-region" aria-busy="true" data-testid="loading-frame">
      <header className="masthead ph-head">
        <div className="page-head">
          <h1>
            <span className="ticker" translate="no">
              {title}
            </span>
            <span className="ph-ghost" style={{ width: 200 }} />
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
      <StepCard title={title} view={view} status="running" headingRef={headingRef} />
      {placeholderPanels(mode).map((panel) => {
        const pair = panel.pairId === undefined ? undefined : pairClass(panel.pairId, stats);
        return (
          <section
            key={panel.name}
            className={pair ? `panel ph-panel ${pair}` : "panel ph-panel"}
            style={{ "--h": `${panel.height}px` } as CSSProperties}
            aria-hidden="true"
            data-placeholder={panel.name}
          >
            <div className="panel-head">
              <h2>{panel.title}</h2>
            </div>
            <div className="ph-body">
              {panel.body === "chart" ? (
                <>
                  <i className="w4" />
                  <i className="blk" />
                  <i className="w2" />
                </>
              ) : (
                LINES.map((w, i) => <i key={i} className={w} />)
              )}
            </div>
          </section>
        );
      })}
    </main>
  );
}
