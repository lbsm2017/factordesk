import type { CSSProperties, Ref } from "react";
import { barFraction } from "../../api/runProgress";
import type { RunView, StepState } from "../../api/runProgress";
import { Icon } from "../shell/icons";

const WORD: Record<StepState, string> = {
  done: "Done",
  running: "Working",
  waiting: "Waiting",
  failed: "Failed",
  "not-run": "Not run",
};
const CLASS: Record<StepState, string> = {
  done: "done",
  running: "run",
  waiting: "wait",
  failed: "fail",
  "not-run": "wait",
};

/** A CSS length from a fraction, for the `--p` custom property of the bars. */
export function percent(fraction: number): string {
  return `${Math.round(fraction * 1000) / 10}%`;
}

/** The inline style that carries a bar's fill. */
export function fill(fraction: number): CSSProperties {
  return { "--p": percent(fraction) } as CSSProperties;
}

export interface StepCardProps {
  /** The ticker (or the name) the run is for. */
  title: string;
  view: RunView;
  /** `running`: the first run is on its way. `failed`: the run stopped at the current step. */
  status: "running" | "failed";
  headingRef?: Ref<HTMLHeadingElement> | undefined;
}

/**
 * The run card (Sprint 4 mockup 1, frames b and f): the steps of one run, with a mark, a name and
 * a word for each, so colour is never the only signal. It sits in the place of the Summary panel.
 * The list is not a live region; the announcer in the page says each step as it starts.
 */
export function StepCard({ title, view, status, headingRef }: StepCardProps) {
  const failed = status === "failed";
  const n = view.current === 0 ? 1 : view.current;
  return (
    <section className={failed ? "panel run-card failed" : "panel run-card"} aria-labelledby="run-title" data-testid="run-card">
      <div className="panel-head">
        <h2 id="run-title" tabIndex={-1} ref={headingRef}>
          {failed ? `The report for ${title} stopped` : `Building the report for ${title}`}
        </h2>
        {view.total > 0 ? <div className="pm">{failed ? `Stopped at step ${n} of ${view.total}` : `Step ${n} of ${view.total}`}</div> : null}
      </div>
      {failed ? null : <p className="q">This takes a few seconds. The report opens here.</p>}
      {!failed && view.total > 0 ? (
        <div className="run-bar" aria-hidden="true" style={fill(barFraction(view))}>
          <i />
        </div>
      ) : null}
      {view.rows.length > 0 ? (
        <ol className="steps">
          {view.rows.map((row, i) => (
            <li key={`${row.id ?? "step"}-${i}`} className={CLASS[row.state]} data-state={row.state}>
              <span className="st-mark" aria-hidden="true">
                {row.state === "done" ? <Icon name="check" /> : row.state === "failed" ? <Icon name="close" /> : null}
              </span>
              <span className="st-name">{row.label}</span>
              <span className="st-state">{WORD[row.state]}</span>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
