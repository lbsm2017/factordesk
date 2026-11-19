/* The table roles below are explicit on purpose (port of add_roles() in render_html.py): narrow
   screens restyle the rows as grids, which can drop the native table semantics. */
/* eslint-disable jsx-a11y/no-redundant-roles, jsx-a11y/no-interactive-element-to-noninteractive-role */
import type { FactorReport } from "../../api/types";
import { useShowStats } from "../../state/stats";
import { exposuresOutcome } from "../../text/outcome";
import { isSubjectReport } from "../../report/subject";
import { exposureReading, plainName } from "../../text/plain";
import { BarCell } from "../charts/BarCell";
import { axisLabels, exposureModel, exposuresUnavailable } from "./exposureModel";
import type { ExposureModel } from "./exposureModel";
import { SigHead } from "./barParts";
import { Panel } from "./Panel";
import type { ReportPanelProps } from "./types";
import "./signColor.css";

const QUESTION = "What is this stock exposed to, and how sure are we?";
const RECORD_QUESTION = "What is this track record exposed to, and how sure are we?";
const DEFAULT_DESC = "Descriptive, in-sample, not predictive.";

/** Sign colour on a beta (owner, 2026-11-19): green above zero, red below; not-significant betas stay grey. */
function betaSignClass(beta: number | null, faded: boolean | undefined): string {
  if (beta === null || faded || beta === 0) return "";
  return beta > 0 ? " num-pos" : " num-neg";
}

function Legend({ window, hasAverages }: { window: number; hasAverages: boolean }) {
  return (
    <ul className="legend" aria-label="Legend">
      <li>
        <svg className="sw" aria-hidden="true">
          <rect className="pos bar-pos" width="14" height="10" rx="2" />
        </svg>
        Positive beta
      </li>
      <li>
        <svg className="sw" aria-hidden="true">
          <rect className="neg bar-neg" width="14" height="10" rx="2" />
        </svg>
        Negative beta
      </li>
      <li>
        <svg className="sw" aria-hidden="true">
          <rect className="neg bar-neg faded" width="14" height="10" rx="2" />
        </svg>
        Faded: not significant
      </li>
      <li>
        <svg className="sw" aria-hidden="true">
          <line className="ci" x1="1" x2="15" y1="5" y2="5" />
          <line className="ci" x1="1" x2="1" y1="3.5" y2="6.5" />
          <line className="ci" x1="15" x2="15" y1="3.5" y2="6.5" />
        </svg>
        95% interval
      </li>
      {hasAverages ? (
        <li>
          <svg className="sw" aria-hidden="true">
            <path className="avgm-sw" d="M8 1.4 11.6 5 8 8.6 4.4 5z" />
          </svg>
          {`Average ${window}d beta`}
        </li>
      ) : null}
    </ul>
  );
}

/** With statistics off the t and average columns are left out (dashboard spec DV5). */
function ExposureTable({ model, stats }: { model: ExposureModel; stats: boolean }) {
  const { domain, rows, window } = model;
  return (
    <table role="table" className={stats ? "bars cols-4" : "bars cols-2"}>
      <caption className="vh">
        Full-sample factor betas with 95% intervals, t-statistics, significance and average rolling beta
      </caption>
      <thead role="rowgroup">
        <tr role="row">
          <th role="columnheader" scope="col">
            Factor
          </th>
          <th role="columnheader" scope="col" className="plot-h">
            <span className="vh">Chart</span>
          </th>
          <th role="columnheader" scope="col" className="num">
            Beta
          </th>
          {stats ? (
            <th role="columnheader" scope="col" className="num">
              t
            </th>
          ) : null}
          <th role="columnheader" scope="col" className="num">
            <SigHead />
          </th>
          {stats ? <th role="columnheader" scope="col" className="num">{`Avg ${window}d`}</th> : null}
        </tr>
      </thead>
      <tbody role="rowgroup">
        {rows.map((r) => (
          <tr key={r.name} role="row" id={`beta-${r.name}`} className={r.faded ? "ns" : undefined} tabIndex={-1}>
            <th role="rowheader" scope="row">
              <span className="fname">{r.name}</span>
              {plainName(r.name) !== r.name ? <span className="sub">{plainName(r.name)}</span> : null}
            </th>
            <td role="cell" className="plot-cell">
              <BarCell
                lo={domain.lo}
                hi={domain.hi}
                ticks={domain.ticks}
                value={r.beta}
                fill="sign"
                faded={r.faded}
                ci={r.ci}
                marker={r.beta === null ? null : r.average}
                title={r.title}
              />
            </td>
            <td role="cell" className={`num strong${betaSignClass(r.beta, r.faded)}`}>
              {r.betaText}
            </td>
            {stats ? (
              <td role="cell" className="num">
                {r.tText}
              </td>
            ) : null}
            <td role="cell" className={`num sig${r.significantText === "Yes" ? " yes" : ""}`}>
              {r.significantText}
            </td>
            {stats ? (
              <td role="cell" className="num">
                {r.averageText}
              </td>
            ) : null}
          </tr>
        ))}
      </tbody>
      <tfoot role="rowgroup">
        <tr role="row" className="axis-row" aria-hidden="true">
          <td role="cell" />
          <td role="cell" className="axis">
            {axisLabels(domain).map((a) => (
              <span key={a.value} className={a.className || undefined} style={{ left: `${a.left}%` }}>
                {a.text}
              </span>
            ))}
          </td>
          <td role="cell" colSpan={stats ? 4 : 2} />
        </tr>
      </tfoot>
    </table>
  );
}

/** What the significance tag (the backend's "reliable") does and does not say (E9a). */
export const NOISE_ONLY =
  "The tag protects against reading noise as a pattern, and nothing more: it does not show that a factor caused the returns or that the model is the right one.";

function footnotes(report: FactorReport, window: number): { footnote: string; how: string } {
  const g = report.regression;
  const texts = report.label_text;
  const desc = texts["L-DESC"] ?? DEFAULT_DESC;
  const more = [
    "Significance uses the Benjamini-Hochberg adjusted p: below 0.05 reads Yes in the Significant column, otherwise No and the row is shown faded.",
    g.caption,
    `The diamond and the Avg ${window}d column are the mean of the overlapping rolling estimates.`,
    ...g.labels.filter((k) => k !== "L-DESC").flatMap((k) => (texts[k] ? [texts[k]] : [])),
  ];
  return {
    footnote: `${desc} Significant means the adjusted p is below 0.05. ${NOISE_ONLY}`,
    how: more.filter(Boolean).join(" "),
  };
}

/** Panel 5 (design D5): betas as an SVG-in-table bar chart. Every number is also a text column. */
export function ExposuresPanel({ report }: ReportPanelProps) {
  const stats = useShowStats();
  const g = report.regression;
  if (exposuresUnavailable(report)) {
    return (
      <Panel
        id="exposures"
        title="Factor exposures"
        question={isSubjectReport(report) ? RECORD_QUESTION : QUESTION}
        empty={{
          reason: g.reason ?? "Insufficient data: no factor betas available.",
          action: "Widen the date range and run the report again.",
        }}
      />
    );
  }
  const model = exposureModel(report);
  const { footnote, how } = footnotes(report, model.window);
  const record = isSubjectReport(report);
  const reading = exposureReading(g.factors, record ? "the record" : undefined);
  return (
    <Panel
      id="exposures"
      title="Factor exposures"
      question={record ? RECORD_QUESTION : QUESTION}
      outcome={exposuresOutcome(report)}
      legend={<Legend window={model.window} hasAverages={model.hasAverages} />}
      reading={reading || undefined}
      footnote={footnote}
      how={how}
    >
      <ExposureTable model={model} stats={stats} />
    </Panel>
  );
}
