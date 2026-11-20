import { useRef, useState } from "react";
import { reportCurrency } from "../../api/currency";
import { dateLong } from "../../format";
import { isSubjectReport, observations, subjectLine } from "../../report/subject";
import { Icon } from "../shell/icons";
import { EurChanges } from "./EurChanges";
import { noticeItems, plural } from "./leadHelpers";
import type { ReportPanelProps } from "./types";
import "./lead.css";

export interface HeaderProps extends ReportPanelProps {
  /** `/api/report/{t}/html?{same range}` for the "Download report" link (DB6.5); null hides the link (an uploaded record has no HTML export). */
  downloadHref: string | null;
}

/**
 * What Yahoo says the ticker is (`data.security`, an optional field of the report). Read loosely:
 * a report without it, or with only some of its parts, shows the ticker alone.
 */
export interface SecurityLike {
  name?: string | null;
  exchange?: string | null;
  currency?: string | null;
  quote_type?: string | null;
}

export function securityOf(report: ReportPanelProps["report"]): SecurityLike {
  const value = (report.data as { security?: SecurityLike | null }).security;
  return value ?? {};
}

const CURRENCY_WORDS: Record<string, string> = { USD: "US dollars" };
const TYPE_BADGE: Record<string, string> = { ETF: "ETF", EQUITY: "Equity" };

/** "Listed on NYSE Arca, priced in US dollars"; a missing part is left out, and both missing give null. */
export function listingLine(security: SecurityLike): string | null {
  const exchange = security.exchange?.trim() || null;
  const code = security.currency?.trim() || null;
  const currency = code === null ? null : (CURRENCY_WORDS[code.toUpperCase()] ?? code);
  if (exchange && currency) return `Listed on ${exchange}, priced in ${currency}`;
  if (exchange) return `Listed on ${exchange}`;
  if (currency) return `Priced in ${currency}`;
  return null;
}

/** The factor set a report was built on: `factor_set` is "europe" for the Europe set and absent for the US one. */
export function reportFactorSet(report: ReportPanelProps["report"]): "us" | "europe" {
  return report.factor_set === "europe" ? "europe" : "us";
}

/**
 * Page header (prototype v4a): the ticker with the company name and the type badge, the listing
 * line, "Download report" on the right, and the analysis bar (analysis period, observations,
 * factor data, factor set, benchmark). It names the factor set in a pill and, in the euro view, opens
 * the "What EUR changes" panel from a link beside the pills.
 */
export function Header({ report, downloadHref }: HeaderProps) {
  const d = report.data;
  const security = securityOf(report);
  const name = security.name?.trim() || null;
  const badge = security.quote_type ? (TYPE_BADGE[security.quote_type.toUpperCase()] ?? null) : null;
  const listing = subjectLine(report) ?? listingLine(security);
  const warnings = noticeItems(report).length;
  const currency = reportCurrency(report);
  const europe = reportFactorSet(report) === "europe";
  const [eurOpen, setEurOpen] = useState(false);
  const eurButton = useRef<HTMLButtonElement>(null);
  return (
    <header className="masthead" id="header">
      <div className="page-head">
        <h1>
          <span className="ticker" translate="no">
            {report.ticker}
          </span>
          {name ? (
            <span className="nm" translate="no">
              {name}
            </span>
          ) : null}
        </h1>
        {badge ? (
          <span className="badge" title="Security type">
            {badge}
          </span>
        ) : null}
        {currency === "EUR" ? <span className="ccy-pill">Figures in EUR</span> : null}
        {europe ? <span className="set-pill">Europe factors</span> : <span className="set-pill plain">US factors</span>}
        {currency === "EUR" ? (
          <button ref={eurButton} type="button" className="hd-link" aria-haspopup="dialog" onClick={() => setEurOpen(true)}>
            <Icon name="info" />
            What EUR changes
          </button>
        ) : null}
        {downloadHref !== null ? (
          <div className="head-actions">
            <a className="btn-outline" href={downloadHref} download>
              <Icon name="download" />
              Download report
            </a>
          </div>
        ) : null}
        {listing ? <p className="listing">{listing}</p> : null}
        {warnings > 0 ? (
          <p className="warn-link">
            <a href="#notice">{plural(warnings, "warning", "warnings")}</a>
          </p>
        ) : null}
      </div>
      <dl className="abar" aria-label="Analysis settings">
        <div>
          <dt>Analysis period</dt>
          <dd>
            {dateLong(d.actual_start)} to {dateLong(d.actual_end)}
          </dd>
        </div>
        <div>
          <dt>Observations</dt>
          <dd>{observations(report, d.n_obs)}</dd>
        </div>
        <div>
          <dt>Factor data</dt>
          <dd title={`${plural(d.factors_days_behind, "day", "days")} old`}>To {dateLong(d.factors_last_date)}</dd>
        </div>
        <div>
          <dt>Factor set</dt>
          <dd>{europe ? "Developed Europe" : "US"}</dd>
        </div>
        {currency === "EUR" ? (
          <div>
            <dt>Currency</dt>
            <dd>EUR</dd>
          </div>
        ) : null}
        {isSubjectReport(report) ? null : (
          <div>
            <dt>Benchmark</dt>
            <dd className="tip" title="ACWI ETF, a stand-in for the MSCI ACWI index">
              ACWI
            </dd>
          </div>
        )}
      </dl>
      {eurOpen && currency === "EUR" ? (
        <EurChanges
          portfolio={report.portfolio_backtest != null}
          returnFocus={eurButton}
          onClose={() => setEurOpen(false)}
        />
      ) : null}
    </header>
  );
}
