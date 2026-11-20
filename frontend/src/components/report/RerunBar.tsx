import { barFraction } from "../../api/runProgress";
import type { RunView } from "../../api/runProgress";
import { fill } from "./StepCard";
import "../../styles/frame.css";

/**
 * A re-run (Sprint 4 mockup 1, frame e): a thin bar sticks to the top of the canvas and a chip under
 * it names the request that is running, because the report on screen may be for another ticker, set
 * or currency. Both are hidden from assistive technology; the page announcer says each step.
 */
export function RerunBar({ title, view }: { title: string; view: RunView }) {
  return (
    <>
      <div className="rr-bar" aria-hidden="true" data-testid="rerun-bar" style={fill(barFraction(view))}>
        <i />
      </div>
      <div className="rr-chip-wrap" aria-hidden="true">
        <p className="rr-chip" data-testid="rerun-chip">
          <span className="dot" />
          <span>Updating {title}</span>
          {view.current > 0 && view.currentLabel !== null ? (
            <span className="sub">{`${view.currentLabel}, step ${view.current} of ${view.total}`}</span>
          ) : null}
        </p>
      </div>
    </>
  );
}
