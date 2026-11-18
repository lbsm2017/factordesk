import type { ReportPanelProps } from "../types";
import { EmptyState } from "../EmptyState";
import { Panel } from "../Panel";

/**
 * Panel of the `shrunk_betas` section (contract SC2.4; spec `docs/specs/shrunk-betas.md`).
 * Registered in `panelRegistry.ts` at position 520. The field holds one section per scope.
 * Owned by the feature branch, which replaces this placeholder body. Renders nothing when the
 * field is absent (null).
 */
export function ShrunkBetasPanel({ report }: ReportPanelProps) {
  const sections = report.shrunk_betas;
  if (sections === null) return null;
  return (
    <Panel
      id="shrunk"
      title="Pulled toward typical"
      question="How far would a stated prior move each beta, and how much data would detect a small one?"
    >
      {sections.map((s, i) =>
        s.status === "ok" ? null : <EmptyState key={i} reason={s.reason ?? ""} action="" />,
      )}
    </Panel>
  );
}
