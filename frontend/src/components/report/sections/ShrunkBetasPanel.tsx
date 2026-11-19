/* The table roles below are explicit on purpose: narrow screens restyle the rows as grids, which
   can drop the native table semantics (design DB7). */
/* eslint-disable jsx-a11y/no-redundant-roles, jsx-a11y/no-interactive-element-to-noninteractive-role */
import type { ShrunkBetas } from "../../../api/types";
import { count, num, pct, signed } from "../../../format";
import { plainName } from "../../../text/plain";
import { position } from "../../charts/BarCell";
import { niceDomain } from "../exposureModel";
import type { NiceDomain } from "../exposureModel";
import { AxisRow, Legend, Swatch } from "../barParts";
import { EmptyState } from "../EmptyState";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import "./ShrunkBetasPanel.css";

const QUESTION = "How far would a stated prior move each beta, and how much data would detect a small one?";
const DEFAULT_DESC = "Descriptive, in-sample, not predictive.";
/** Shrinkage is drawn only for a pull of at least this share (spec SB6 rule 2). */
const MIN_VISIBLE_PULL = 0.05;
const NO_PULL_LINE = "Shrinkage moves no beta by a visible amount: this sample is long enough.";
const NOTHING = "n/a";
/* The words below are the words of the static panel (backend/factordesk/report/panels/shrunk.py); a
   test on each side pins them, so a change here needs the same change there. */
const LEGEND_TEXT = "Pull of 5% or more";
const PULL_NOTE =
  "Pull is the weight the prior gets on this beta by itself: 0% means none, 100% means all. Because the factors are estimated together, the beta can move less, more, or away from its typical value.";
const POWER_HEADING = "What the test behind the reliable tags could detect";
const CAPTION =
  "OLS and shrunk betas with standard errors, 95% credible intervals and pull; a marker is drawn only where the pull is at least 5%";
type ShrunkBeta = ShrunkBetas["betas"][number];
const CROSS_SECTION_WORDS: Record<string, string> = { industry49: "industry", size_char75: "size" };

interface Row {
  beta: ShrunkBeta;
  /** The shrunk marker and its credible interval are drawn (pull of at least 0.05). */
  marked: boolean;
  /** Pull clipped to [0, 1]; null when the model gave none. */
  pull: number | null;
  /** The shrunk beta sits on the far side of the OLS beta from the prior centre. */
  movedAway: boolean;
  cred: { low: number; high: number } | null;
}

function finite(x: number | null | undefined): number | null {
  return typeof x === "number" && Number.isFinite(x) ? x : null;
}

function rowOf(beta: ShrunkBeta): Row {
  const raw = finite(beta.pull);
  const pull = raw === null ? null : Math.min(Math.max(raw, 0), 1);
  const shrunk = finite(beta.beta_shrunk);
  const low = finite(beta.cred95_low);
  const high = finite(beta.cred95_high);
  const marked = pull !== null && pull >= MIN_VISIBLE_PULL && shrunk !== null;
  return {
    beta,
    marked,
    pull,
    movedAway: marked && beta.moved_away === true,
    cred: low !== null && high !== null ? { low, high } : null,
  };
}

function domainOf(rows: readonly Row[]): NiceDomain {
  const values = [0];
  for (const r of rows) {
    values.push(r.beta.beta_ols);
    if (r.marked) {
      const s = finite(r.beta.beta_shrunk);
      if (s !== null) values.push(s);
      if (r.cred) values.push(r.cred.low, r.cred.high);
    }
  }
  return niceDomain(Math.min(...values), Math.max(...values), 5);
}

function sgn(x: number | null): string {
  return x === null ? NOTHING : signed(x);
}

function credText(r: Row): string {
  return r.cred ? `[${signed(r.cred.low)}, ${signed(r.cred.high)}]` : NOTHING;
}

function pullText(r: Row): string {
  return r.pull === null ? NOTHING : pct(r.pull, 1, false);
}

/** The spoken form of the shrunk marker, used for the tooltip and for screen readers. */
function markerText(r: Row): string {
  const { beta } = r;
  // A row that moved away is never described as pulled toward typical.
  const move = r.movedAway ? "moved away from its typical value to" : "pulled toward typical to";
  return (
    `${beta.factor}: OLS beta ${signed(beta.beta_ols)}; ${move} ${sgn(finite(beta.beta_shrunk))}, ` +
    `95% credible interval ${r.cred ? `${signed(r.cred.low)} to ${signed(r.cred.high)}` : NOTHING}, ` +
    `pull ${pullText(r)}`
  );
}

function plainTitle(r: Row): string {
  return r.marked ? markerText(r) : `${r.beta.factor}: OLS beta ${signed(r.beta.beta_ols)}, not visibly pulled`;
}

function ShrunkPlot({ row, domain }: { row: Row; domain: NiceDomain }) {
  const { lo, hi, ticks } = domain;
  const zero = position(0, lo, hi);
  const ols = row.beta.beta_ols;
  const [a = 0, b = 0] = [zero, position(ols, lo, hi)].sort((x, y) => x - y);
  const shrunk = finite(row.beta.beta_shrunk);
  const credLo = row.cred ? `${position(row.cred.low, lo, hi)}%` : "";
  const credHi = row.cred ? `${position(row.cred.high, lo, hi)}%` : "";
  return (
    <svg className="bar-svg" aria-hidden="true">
      <title>{plainTitle(row)}</title>
      {ticks.map((t) => {
        const x = `${position(t, lo, hi)}%`;
        return <line key={t} className={Math.abs(t) < 1e-12 ? "zero" : "grid"} x1={x} x2={x} y1="0" y2="100%" />;
      })}
      <rect className={ols >= 0 ? "pos" : "neg"} x={`${a}%`} y="32%" width={`${Math.max(b - a, 0)}%`} height="36%" rx="2" />
      {row.marked && row.cred ? (
        <>
          <line className="cred" x1={credLo} x2={credHi} y1="50%" y2="50%" />
          <line className="cred" x1={credLo} x2={credLo} y1="44%" y2="56%" />
          <line className="cred" x1={credHi} x2={credHi} y1="44%" y2="56%" />
        </>
      ) : null}
      {row.marked && shrunk !== null ? (
        <svg className="shrm" x={`${position(shrunk, lo, hi)}%`} y="50%" overflow="visible" aria-hidden="true">
          <path d="M0 -4.5 4.5 0 0 4.5-4.5 0z" />
        </svg>
      ) : null}
    </svg>
  );
}

function MovedAway({ row }: { row: Row }) {
  const up = (finite(row.beta.beta_shrunk) ?? 0) > row.beta.beta_ols;
  return (
    <span className="sub moved">
      <span aria-hidden="true">{up ? "↗" : "↘"}</span> Moved away from typical
    </span>
  );
}

function ShrunkTable({ id, rows, domain }: { id: string; rows: readonly Row[]; domain: NiceDomain }) {
  return (
    <table role="table" className="bars shrunk" aria-labelledby={`${id}-h`}>
      <caption className="vh">{CAPTION}</caption>
      <thead role="rowgroup">
        <tr role="row">
          <th role="columnheader" scope="col">
            Factor
          </th>
          <th role="columnheader" scope="col" className="plot-h">
            <span className="vh">Chart</span>
          </th>
          <th role="columnheader" scope="col" className="num">
            OLS beta
          </th>
          <th role="columnheader" scope="col" className="num">
            se
          </th>
          <th role="columnheader" scope="col" className="num">
            Shrunk beta
          </th>
          <th role="columnheader" scope="col" className="num">
            95% credible interval
          </th>
          <th role="columnheader" scope="col" className="num">
            Pull
          </th>
        </tr>
      </thead>
      <tbody role="rowgroup">
        {rows.map((r) => {
          const f = r.beta.factor;
          return (
            <tr key={f} role="row" id={`${id}-${f}`} tabIndex={-1}>
              <th role="rowheader" scope="row">
                <span className="fname">{f}</span>
                {plainName(f) !== f ? <span className="sub">{plainName(f)}</span> : null}
                {r.movedAway ? <MovedAway row={r} /> : null}
              </th>
              <td role="cell" className="plot-cell">
                <ShrunkPlot row={r} domain={domain} />
                {r.marked ? <span className="vh">{markerText(r)}</span> : null}
              </td>
              <td role="cell" className="num strong ols" data-label="OLS">
                {signed(r.beta.beta_ols)}
              </td>
              <td role="cell" className="num se" data-label="se">
                {num(r.beta.se_hac)}
              </td>
              <td role="cell" className="num strong shr" data-label="Shrunk">
                {sgn(finite(r.beta.beta_shrunk))}
              </td>
              <td role="cell" className="num range ci-text" data-label="95% credible interval">
                {credText(r)}
              </td>
              <td role="cell" className="num pull" data-label="Pull">
                {pullText(r)}
              </td>
            </tr>
          );
        })}
      </tbody>
      <tfoot role="rowgroup">
        <AxisRow
          ticks={domain.ticks}
          lo={domain.lo}
          hi={domain.hi}
          format={(t) => (t === 0 ? "0" : signed(t, 2))}
          columns={5}
        />
      </tfoot>
    </table>
  );
}

function scopeTitle(s: ShrunkBetas): string {
  if (s.scope === "full_sample") return `Full sample (${count(s.sample.n)} days)`;
  return s.window === null ? "Latest window" : `Latest ${s.window}-day window`;
}

function nextStep(s: ShrunkBetas): string {
  return s.status === "insufficient_data"
    ? "Widen the date range and run the report again."
    : "Run the report again; if it repeats, check the factor data in Data and audit.";
}

function ScopeBlock({ s }: { s: ShrunkBetas }) {
  const id = `shrunk-${s.scope}`;
  const title = scopeTitle(s);
  if (s.status !== "ok") {
    return (
      <div className="shrunk-scope">
        <h3 id={`${id}-h`}>{title}</h3>
        <EmptyState reason={s.reason ?? "No shrunk betas for this scope."} action={nextStep(s)} />
      </div>
    );
  }
  const rows = s.betas.map(rowOf);
  const domain = domainOf(rows);
  const powers = s.power.flatMap((p) => (p.text ? [{ factor: p.factor, text: p.text }] : []));
  return (
    <div className="shrunk-scope">
      <h3 id={`${id}-h`}>{title}</h3>
      {rows.some((r) => r.marked) ? null : <p className="reading">{NO_PULL_LINE}</p>}
      <ShrunkTable id={id} rows={rows} domain={domain} />
      <p className="pull-note">{PULL_NOTE}</p>
      {powers.length > 0 ? (
        <>
          <h4 className="power-h">{POWER_HEADING}</h4>
          <ul className="power" aria-label={`Power statements, ${title}`}>
            {powers.map((p) => (
              <li key={p.factor}>{p.text}</li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}

function priorSentence(sections: readonly ShrunkBetas[]): string {
  const source = sections.find((s) => s.status === "ok" && s.prior !== null);
  const prior = source?.prior;
  if (!source || !prior) return "";
  const perFactor = source.betas
    .map((b, i) => {
      const centre = finite(prior.centre[i]);
      const tau = finite(prior.tau[i]);
      return centre === null || tau === null ? "" : `${b.factor} ${num(centre)} and ${num(tau)}`;
    })
    .filter(Boolean)
    .join("; ");
  const sizes = Object.entries(prior.n_portfolios)
    .map(([k, n]) => `${n} ${CROSS_SECTION_WORDS[k] ?? k}`)
    .join(" and ");
  return (
    `Prior centre and spread per factor: ${perFactor}. ` +
    `The spread comes from ${sizes} portfolios, ${prior.window_start} to ${prior.window_end}.`
  );
}

/**
 * Panel of the `shrunk_betas` section (contract SC2.4; spec `docs/specs/shrunk-betas.md`). One block per
 * scope (full sample, then the latest window): the OLS beta as the bar, the beta pulled toward typical as
 * a hollow diamond with its credible interval, every number also in a column. Renders nothing when the
 * field is absent (null).
 */
export function ShrunkBetasPanel({ report }: ReportPanelProps) {
  const sections = report.shrunk_betas;
  if (sections === null) return null;
  const texts = report.label_text;
  const ok = sections.filter((s) => s.status === "ok");
  const anyMark = ok.some((s) => s.betas.some((b) => rowOf(b).marked));
  // The word and the label L-CORR-MOVE belong to rows whose pull marker is drawn.
  const anyMoved = ok.some((s) => s.betas.some((b) => rowOf(b).movedAway));
  const listed = [...new Set(ok.flatMap((s) => s.labels))].filter(
    (k) => k !== "L-DESC" && (anyMoved || k !== "L-CORR-MOVE"),
  );
  const how = [priorSentence(sections), ...listed.flatMap((k) => (texts[k] ? [texts[k]] : []))]
    .filter(Boolean)
    .join(" ");
  const legend =
    ok.length === 0 ? undefined : (
      <Legend
        items={[
          <>
            <Swatch kind="pos" />
            OLS beta
          </>,
          ...(anyMark
            ? [
                <>
                  <svg className="sw" aria-hidden="true">
                    <line className="cred" x1="1" x2="15" y1="5" y2="5" />
                    <path className="shrm-sw" d="M8 0.8 12.2 5 8 9.2 3.8 5z" />
                  </svg>
                  {LEGEND_TEXT}
                </>,
              ]
            : []),
        ]}
      />
    );
  return (
    <Panel
      id="shrunk"
      title="Adjusted for noise"
      question={QUESTION}
      legend={legend}
      footnote={ok.length === 0 ? undefined : (texts["L-DESC"] ?? DEFAULT_DESC)}
      how={ok.length === 0 ? undefined : how || undefined}
    >
      {sections.map((s) => (
        <ScopeBlock key={s.scope} s={s} />
      ))}
    </Panel>
  );
}
