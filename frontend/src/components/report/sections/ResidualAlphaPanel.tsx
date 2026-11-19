import { lazy, Suspense } from "react";
import { Panel } from "../Panel";
import { PanelBoundary } from "../PanelBoundary";
import type { ReportPanelProps } from "../types";

export const TITLE = "Beyond the factors";
export const DEFAULT_QUESTION =
  "What did this stock return beyond its factor exposures, and does it hold up without hindsight?";

/** The panel body is its own chunk: it is large and only reports with the section need it. */
const Body = lazy(() => import("./ResidualAlphaBody").then((m) => ({ default: m.ResidualAlphaBody })));

/**
 * Panel of the `residual` section (contract SC2.5; spec `docs/methodology-residual-analysis.md`).
 * Registered in `panelRegistry.ts` at position 710. Renders nothing when the section is absent
 * (null); while the body chunk loads, the empty frame (title and question) holds its place. A
 * failure inside the body (or its chunk) shows a plain notice in the same frame and leaves the
 * rest of the report on screen.
 */
export function ResidualAlphaPanel({ report }: ReportPanelProps) {
  const section = report.residual;
  if (section === null) return null;
  const question = section.question || DEFAULT_QUESTION;
  return (
    <PanelBoundary id="residual" title={TITLE} question={question}>
      <Suspense fallback={<Panel id="residual" title={TITLE} question={question} />}>
        <Body report={report} />
      </Suspense>
    </PanelBoundary>
  );
}
