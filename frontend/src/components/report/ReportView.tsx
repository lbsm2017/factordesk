import type { FactorReport } from "../../api/types";
import type { RollingWindowDays } from "../../state/url";
import "../../styles/frame.css";
import { Hatch } from "../charts/Hatch";
import { Colophon } from "./Colophon";
import { DataAuditPanel } from "./DataAuditPanel";
import { Equation } from "./Equation";
import { ExposuresPanel } from "./ExposuresPanel";
import { Header } from "./Header";
import { KpiStrip } from "./KpiStrip";
import { Notice } from "./Notice";
import { PricePanel } from "./PricePanel";
import { RegressionDetail } from "./RegressionDetail";
import { ReturnPanel } from "./ReturnPanel";
import { RiskPanel } from "./RiskPanel";
import { RollingPanel } from "./RollingPanel";

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

/**
 * Places every panel in the report's order (design C). Panel tickets never edit this file:
 * add a panel by filling its own file.
 */
export function ReportView({ report, downloadHref, win, onWinChange, busy = false }: ReportViewProps) {
  const primary: RollingWindowDays = report.average_beta.window === 126 ? 126 : 252;
  return (
    <main className="report-region" aria-busy={busy} data-testid="report-region">
      <Hatch />
      <Header report={report} downloadHref={downloadHref} />
      <Notice report={report} />
      <Equation report={report} />
      <KpiStrip report={report} />
      <PricePanel report={report} />
      <ExposuresPanel report={report} />
      <ReturnPanel report={report} />
      <RiskPanel report={report} />
      <RollingPanel report={report} win={win ?? primary} onWinChange={onWinChange} />
      <DataAuditPanel report={report} />
      <RegressionDetail report={report} />
      <Colophon report={report} />
    </main>
  );
}
