/**
 * Ordered panel registry of the report page (schema v3 contract, SC3.4 and SC4). `ReportView` draws
 * `orderedPanels()` in position order. Names and positions match the static report's registry
 * (`backend/factordesk/report/panel_registry.py`) where they exist there; `summary` replaces the old
 * notice, equation and KPI strip, and carries the data notes (anchor `#notice`).
 *
 * The optional sections are already listed, each pointing at its own component under
 * `sections/`; a feature fills its component in and never edits this file. Each of those
 * components renders nothing while its report field is null.
 */
import type { ComponentType } from "react";
import type { FactorReport } from "../../api/types";
import type { RollingWindowDays } from "../../state/url";
import { Colophon } from "./Colophon";
import { DataAuditPanel } from "./DataAuditPanel";
import { ExposuresPanel } from "./ExposuresPanel";
import { Header } from "./Header";
import { PricePanel } from "./PricePanel";
import { RegressionDetail } from "./RegressionDetail";
import { ReturnPanel } from "./ReturnPanel";
import { RiskPanel } from "./RiskPanel";
import { RollingPanel } from "./RollingPanel";
import { SummaryPanel } from "./SummaryPanel";
import { FragilityPanel } from "./sections/FragilityPanel";
import { LazyKalmanPanel, LazyShrunkBetasPanel } from "./sections/lazySections";
import { LeadLagPanel } from "./sections/LeadLagPanel";
import { PerformancePanel } from "./sections/PerformancePanel";
import { ResidualAlphaPanel } from "./sections/ResidualAlphaPanel";
import { WorldBetaPanel } from "./sections/WorldBetaPanel";

/** What `ReportView` hands to every panel; each panel reads the props it needs. */
export interface PanelHostProps {
  report: FactorReport;
  /** `/api/report/{t}/html?{same range}`, for the Download link in the header. */
  downloadHref: string;
  /** Rolling window shown (the URL's `win`, or the report's primary window). */
  win: RollingWindowDays;
  onWinChange: (win: RollingWindowDays) => void;
}

export interface PanelEntry {
  /** Stable name, the same as in the static report's registry. */
  name: string;
  /** Place on the page; lower comes first (contract SC4). */
  position: number;
  Component: ComponentType<PanelHostProps>;
}

export const PANELS: readonly PanelEntry[] = [
  { name: "header", position: 100, Component: Header },
  { name: "summary", position: 200, Component: SummaryPanel },
  { name: "price", position: 400, Component: PricePanel },
  { name: "performance", position: 450, Component: PerformancePanel },
  { name: "exposures", position: 500, Component: ExposuresPanel },
  { name: "world_beta", position: 505, Component: WorldBetaPanel },
  { name: "lead_lag", position: 510, Component: LeadLagPanel },
  { name: "shrunk", position: 520, Component: LazyShrunkBetasPanel },
  { name: "fragility", position: 530, Component: FragilityPanel },
  { name: "returns", position: 600, Component: ReturnPanel },
  { name: "risk", position: 700, Component: RiskPanel },
  { name: "residual_alpha", position: 710, Component: ResidualAlphaPanel },
  { name: "rolling", position: 800, Component: RollingPanel },
  { name: "kalman", position: 810, Component: LazyKalmanPanel },
  { name: "data", position: 900, Component: DataAuditPanel },
  { name: "regression_detail", position: 1000, Component: RegressionDetail },
  { name: "colophon", position: 1100, Component: Colophon },
];

/** The entries by position. Throws when a name or a position is used twice. */
export function orderedPanels(entries: readonly PanelEntry[] = PANELS): PanelEntry[] {
  const names = new Set<string>();
  const positions = new Set<number>();
  for (const entry of entries) {
    if (names.has(entry.name)) throw new Error(`panel name "${entry.name}" is registered twice`);
    if (positions.has(entry.position)) throw new Error(`panel position ${entry.position} is taken twice`);
    names.add(entry.name);
    positions.add(entry.position);
  }
  return [...entries].sort((a, b) => a.position - b.position);
}
