import { Panel } from "./Panel";
import type { ReportPanelProps } from "./types";

export interface HeaderProps extends ReportPanelProps {
  /** `/api/report/{t}/html?{same range}` for the "Download report" link (DB6.5). */
  downloadHref: string;
}

/** STUB (T5): fill in this file only. Props are fixed by T3. */
export function Header({ report }: HeaderProps) {
  return <Panel id="header" title={report.ticker} />;
}
