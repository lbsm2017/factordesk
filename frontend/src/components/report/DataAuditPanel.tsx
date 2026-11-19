import type { AuditFinding, FactorReport } from "../../api/types";
import { count, dateLong, pct } from "../../format";
import { isSubjectReport, observations, periodWord } from "../../report/subject";
import { dataOutcome } from "../../text/outcome";
import { Panel } from "./Panel";
import type { ReportPanelProps } from "./types";

/** Plain wording of each exclusion reason code (ported from the static renderer). */
const EXCLUSION_TEXT: Record<string, string> = {
  multi_day_return: "return spans several factor days",
  no_factor_row: "date not in the factor file",
  price_missing: "price missing",
  factor_missing: "factor value missing",
};

const DATES_LIMIT = 6;

/** Glyph by severity (design D): a shape plus a word, never colour alone. */
function Glyph({ severity }: { severity: AuditFinding["severity"] }) {
  if (severity === "warning") {
    return (
      <svg className="glyph" aria-hidden="true" viewBox="0 0 16 16">
        <path d="M8 1.5 15 14.5H1z" />
        <path className="cut" d="M8 6v4M8 11.6v1" />
      </svg>
    );
  }
  if (severity === "error") {
    return (
      <svg className="glyph" aria-hidden="true" viewBox="0 0 16 16">
        <rect x="2" y="2" width="12" height="12" rx="1" />
        <path className="cut" d="M5.5 5.5l5 5M10.5 5.5l-5 5" />
      </svg>
    );
  }
  return (
    <svg className="glyph" aria-hidden="true" viewBox="0 0 16 16">
      <circle cx="8" cy="8" r="6.5" />
      <path className="cut" d="M8 7v4.5M8 4.6v.9" />
    </svg>
  );
}

/** " (8 Aug 2024, ... and 3 more)": up to six dates, then a count of the rest. */
function datesText(dates: readonly string[]): string {
  if (!dates.length) return "";
  const shown = dates.slice(0, DATES_LIMIT).map(dateLong).join(", ");
  const more = dates.length - DATES_LIMIT;
  return ` (${shown}${more > 0 ? ` and ${more} more` : ""})`;
}

/** "2026-11-01T00:00:00Z" as "1 Nov 2026, 00:00 UTC" (the API sends UTC). */
function downloadedText(iso: string | null): string {
  if (!iso) return "Injected, not downloaded";
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(iso);
  return m ? `${dateLong(m[1] as string)}, ${m[2]} UTC` : iso;
}

function coverage(report: FactorReport): [string, string][] {
  const d = report.data;
  const reasons = Object.entries(d.excluded_by_reason)
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([k, v]) => `${v} ${EXCLUSION_TEXT[k] ?? k}`)
    .join(", ");
  const unc = d.uncovered;
  const after = unc.n
    ? `${count(unc.n)} ${periodWord(report)} (raw return ${unc.compounded_return === null ? "n/a" : pct(unc.compounded_return)}, not analysed)`
    : "none";
  return [
    ["Requested", `${dateLong(d.requested_start)} to ${dateLong(d.requested_end)}`],
    [
      "Analysed",
      `${dateLong(d.actual_start)} to ${dateLong(d.actual_end)}, ${observations(report, d.n_obs)}`,
    ],
    ["Excluded inside the range", `${count(d.n_excluded)}${reasons ? ` (${reasons})` : ""}`],
    ["After factor data", after],
    ["Before factor data", `${count(d.dropped_price_dates_before_factors)} ${periodWord(report)}`],
    ["Factor data ends", `${dateLong(d.factors_last_date)}, ${count(d.factors_days_behind)} days before the report`],
    ["Factor file downloaded", downloadedText(d.factors_downloaded_at)],
    [isSubjectReport(report) ? "Returns" : "Prices", d.price_source],
    // Plain text on purpose: the report never links out.
    ["Factors", d.factors_source_url],
  ];
}

/** Data and audit: coverage, audit findings, caveats. Findings are reported, never acted on. */
export function DataAuditPanel({ report }: ReportPanelProps) {
  const d = report.data;
  const findings = d.audit_findings;
  const notes = [...report.notes];
  const vintage = report.label_text?.["L-VINTAGE"];
  if (vintage && !notes.includes(vintage)) notes.push(vintage);
  return (
    <Panel
      id="data"
      title="Data and audit"
      question="What went into these numbers, and what was left out?"
      outcome={dataOutcome(report)}
      footnote="Audit findings are reported, never acted on: no price is changed or removed."
    >
      <div className="data-grid">
        <div>
          <h3>Coverage</h3>
          <dl className="facts">
            {coverage(report).map(([term, value]) => (
              <div key={term}>
                <dt>{term}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div>
          <h3>Audit findings</h3>
          <ul className="findings">
            {findings.length ? (
              findings.map((f, i) => (
                <li key={`${f.code}-${i}`} className={`sev-${f.severity}`}>
                  <Glyph severity={f.severity} />
                  <span className="sev">{f.severity.charAt(0).toUpperCase() + f.severity.slice(1)}</span>
                  <span className="msg">
                    {f.message}
                    <span className="dates">{datesText(f.dates)}</span>
                  </span>
                </li>
              ))
            ) : (
              <li className="sev-none">
                <span className="msg">{`No findings. ${isSubjectReport(report) ? "The returns" : "Prices"} passed every check.`}</span>
              </li>
            )}
          </ul>
          <h3>Caveats</h3>
          <ul className="notes">
            {notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      </div>
    </Panel>
  );
}
