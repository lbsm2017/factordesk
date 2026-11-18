import { dateLong } from "../../format";
import { noticeItems, plural } from "./leadHelpers";
import type { ReportPanelProps } from "./types";
import "./lead.css";

export interface HeaderProps extends ReportPanelProps {
  /** `/api/report/{t}/html?{same range}` for the "Download report" link (DB6.5). */
  downloadHref: string;
}

/** Ticker, factor-data chip, warnings chip and the Download link (design 1, DB6.5). */
export function Header({ report, downloadHref }: HeaderProps) {
  const d = report.data;
  const warnings = noticeItems(report).length;
  return (
    <header className="masthead" id="header">
      <div className="mast-top">
        <h1>
          <span className="ticker">{report.ticker}</span>
          <span className="what">Fama–French five-factor profile</span>
        </h1>
        <p className="mast-meta">
          <span className="chip">
            Factor data ends {dateLong(d.factors_last_date)} ({plural(d.factors_days_behind, "day", "days")} ago)
          </span>
          {warnings > 0 ? (
            <a className="chip warn" href="#notice">
              {plural(warnings, "warning", "warnings")}
            </a>
          ) : null}
          <a className="btn-secondary" href={downloadHref} download>
            Download report
          </a>
        </p>
      </div>
    </header>
  );
}
