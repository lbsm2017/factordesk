import { lazy, Suspense } from "react";
import { Panel } from "../Panel";
import { PanelBoundary } from "../PanelBoundary";
import type { ReportPanelProps } from "../types";

const TITLE = "Drawdown";

/** The panel body is its own chunk, as for the residual panel: it holds the chart code. */
const Body = lazy(() => import("./PerformanceBody").then((m) => ({ default: m.PerformanceBody })));

/**
 * Panel of the `performance` section (contract note `docs/validation/performance-contract-note-2026-11-18.md`):
 * the underwater chart and the largest falls. Registered in `panelRegistry.ts` at position 450, right
 * after Price. Renders nothing when the section is absent (null); the summary tiles of the same
 * section live in the Summary.
 */
export function PerformancePanel({ report }: ReportPanelProps) {
  if (report.performance === null) return null;
  return (
    <PanelBoundary id="performance" title={TITLE} question="">
      <Suspense fallback={<Panel id="performance" title={TITLE} />}>
        <Body report={report} />
      </Suspense>
    </PanelBoundary>
  );
}
