import type { ReportPanelProps } from "../types";
import { Panel } from "../Panel";

/**
 * Panel of the `world_beta` section (quick beta against the iShares MSCI ACWI ETF; backend
 * `report/sections/world_beta.py`, handoff `docs/validation/world-beta-handoff-2026-11-18.md`).
 * Registered in `panelRegistry.ts` at position 540. Placeholder: the panel frame, with the reason
 * when the section is not `ok`; the real body is built later. Renders nothing when the section is
 * absent (null).
 */
export function WorldBetaPanel({ report }: ReportPanelProps) {
  const section = report.world_beta;
  if (section === null) return null;
  const empty = section.status === "ok" ? {} : { empty: { reason: section.reason ?? "", action: "" } };
  return (
    <Panel
      id="world-beta"
      title="World beta (quick estimate)"
      question="How much does this stock move with the world market, next to the US market?"
      {...empty}
    />
  );
}
