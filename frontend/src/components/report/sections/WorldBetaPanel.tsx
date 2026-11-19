import { lazy, Suspense } from "react";
import { Panel } from "../Panel";
import { PanelBoundary } from "../PanelBoundary";
import type { ReportPanelProps } from "../types";

const TITLE = "World beta";

/** The panel body is its own chunk, as for the residual panel. */
const Body = lazy(() => import("./WorldBetaBody").then((m) => ({ default: m.WorldBetaBody })));

/**
 * Panel of the `world_beta` section (quick beta against the iShares MSCI ACWI ETF; backend
 * `report/sections/world_beta.py`, handoff `docs/validation/world-beta-handoff-2026-11-18.md`).
 * Registered in `panelRegistry.ts` at position 505, right after Factor exposures. Renders nothing when the section is absent (null).
 */
export function WorldBetaPanel({ report }: ReportPanelProps) {
  if (report.world_beta === null) return null;
  return (
    <PanelBoundary id="world-beta" title={TITLE} question="">
      <Suspense fallback={<Panel id="world-beta" title={TITLE} />}>
        <Body report={report} />
      </Suspense>
    </PanelBoundary>
  );
}
