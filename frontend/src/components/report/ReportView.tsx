import type { FactorReport } from "../../api/types";
import type { RollingWindowDays } from "../../state/url";
import "../../styles/frame.css";
import { Hatch } from "../charts/Hatch";
import { orderedPanels } from "./panelRegistry";
import type { PanelHostProps } from "./panelRegistry";

export interface ReportViewProps {
  report: FactorReport;
  /** `/api/report/{t}/html?{same range}`, for the Download link in the header. */
  downloadHref: string;
  /** Rolling window from the URL (`win`); null means the report's primary window. */
  win: RollingWindowDays | null;
  onWinChange: (win: RollingWindowDays) => void;
  /** A new request is running: `aria-busy` on the region (KPI values and ticker show placeholders). */
  busy?: boolean;
}

/** Panel order, checked once (contract SC4): a repeated name or position fails at load. */
const PANELS_IN_ORDER = orderedPanels();

/**
 * Places every panel in the report's order (design C) from the panel registry (`panelRegistry.ts`,
 * schema v3 contract). Panel tickets never edit this file: add a panel by filling its own file.
 */
export function ReportView({ report, downloadHref, win, onWinChange, busy = false }: ReportViewProps) {
  const primary: RollingWindowDays = report.average_beta.window === 126 ? 126 : 252;
  const host: PanelHostProps = { report, downloadHref, win: win ?? primary, onWinChange };
  return (
    <main className="report-region" aria-busy={busy} data-testid="report-region">
      <Hatch />
      {PANELS_IN_ORDER.map(({ name, Component }) => (
        <Component key={name} {...host} />
      ))}
    </main>
  );
}
