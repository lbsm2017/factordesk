/* eslint-disable jsx-a11y/no-redundant-roles, jsx-a11y/no-interactive-element-to-noninteractive-role --
   DB7 asks for explicit table roles: the narrow-screen CSS restyles rows as grids, which can drop table semantics. */
import { useMemo } from "react";
import type { FactorReport, KalmanBetaSeries } from "../../../api/types";
import type { components } from "../../../api/types.gen";
import { count, dateLong, num, pct, signed } from "../../../format";
import { dateTicks, factorOrder, finite, isoMs, labelTexts, slotOf } from "../../../report/derive";
import text from "../../../text/kalman.json";
import { PLAIN } from "../../../text/plain";
import { KeySwatch } from "../barParts";
import { Panel } from "../Panel";
import { narrowTicks } from "../RollingPanel";
import type { ReportPanelProps } from "../types";
import "./KalmanPanel.css";

type KalmanVintage = components["schemas"]["KalmanVintage"];
type KalmanLatest = components["schemas"]["KalmanLatest"];

/**
 * Every sentence, header and flag below comes from `text/kalman.json`, a copy of the backend file
 * `report/kalman_text.json` that the static panel reads too (a test on each side compares them).
 * Placeholders are written `{name}`.
 */
const TITLE = "Tracked day by day";
const QUESTION = text.question;

function fill(template: string, values: Record<string, string | number>): string {
  return Object.entries(values).reduce((out, [key, value]) => out.replaceAll(`{${key}}`, String(value)), template);
}

/** Same padding on the common vertical span as the rolling panel. */
const SPAN_PADDING = 1.08;
/** A series up to this many points is drawn as it is; a longer one is thinned. */
export const MAX_DRAWN_POINTS = 1500;
/** Buckets used when thinning: each keeps its first and last point and its extremes. */
export const THIN_BUCKETS = 300;

/** Sentences for the warning codes of the section (backend `WARNING_TEXT`). */
const WARNING_TEXT: Record<string, string> = text.warnings;

/** The flag of a drift rate at a limit; a rate within limits has none. */
const BOUND_WORDS: Record<KalmanVintage["lam_at_bound"], string> = { ...text.bound, none: "" };

// ---------------------------------------------------------------------------- thinning

/**
 * Min-max thinning for drawing. `series` are equally long arrays; the result is the sorted indices
 * to draw. Each of `THIN_BUCKETS` buckets keeps its first and last point and the position of the
 * lowest and highest value of every series, so a one-day spike always survives. A series of at most
 * `maxPoints` is returned whole. All numbers shown as text come from the full series.
 */
export function thinIndices(series: readonly (readonly number[])[], maxPoints = MAX_DRAWN_POINTS): number[] {
  const n = series[0]?.length ?? 0;
  if (n <= maxPoints) return Array.from({ length: n }, (_, i) => i);
  const size = Math.ceil(n / THIN_BUCKETS);
  const keep: number[] = [];
  for (let start = 0; start < n; start += size) {
    const end = Math.min(start + size, n);
    const chosen = new Set<number>([start, end - 1]);
    for (const values of series) {
      let lo = start;
      let hi = start;
      for (let i = start + 1; i < end; i++) {
        if ((values[i] as number) < (values[lo] as number)) lo = i;
        if ((values[i] as number) > (values[hi] as number)) hi = i;
      }
      chosen.add(lo);
      chosen.add(hi);
    }
    keep.push(...[...chosen].sort((a, b) => a - b));
  }
  return keep;
}

// ---------------------------------------------------------------------------- model

export interface KalmanRowData {
  name: string;
  plain: string;
  slot: 1 | 2 | 3 | 4 | 5 | 6;
  /** The section's `latest` entry; null when the report has none for this factor. */
  latest: KalmanLatest | null;
  /** Number of dated values (after warm-up) and of points drawn after thinning. */
  total: number;
  drawn: number;
  /** SVG path data in a 1000 by 100 box: the beta line and the band polygon. */
  line: string;
  band: string;
  /** Vertical span of this row: the common span, centred on the row's own band. */
  lo: number;
  hi: number;
  /** Extremes of the beta line itself, from the full series. */
  min: number;
  max: number;
}

export interface KalmanModel {
  rows: KalmanRowData[];
  /** First and last date shown (ISO) and in ms. */
  first: string;
  last: string;
  from: number;
  to: number;
  /** Positions in percent of the yearly re-estimates after the first (where the line can jump). */
  cuts: number[];
}

interface Dense {
  name: string;
  idx: number[];
  beta: number[];
  low: number[];
  high: number[];
}

/** The rows of one factor that have a beta and a band (warm-up rows drop out). */
function densify(s: KalmanBetaSeries, name: string): Dense | null {
  const betas = s.betas[name] ?? [];
  const lows = s.band_low[name] ?? [];
  const highs = s.band_high[name] ?? [];
  const n = Math.min(betas.length, lows.length, highs.length, s.dates.length);
  const out: Dense = { name, idx: [], beta: [], low: [], high: [] };
  for (let i = 0; i < n; i++) {
    const b = finite(betas[i]);
    const lo = finite(lows[i]);
    const hi = finite(highs[i]);
    if (b === null || lo === null || hi === null) continue;
    out.idx.push(i);
    out.beta.push(b);
    out.low.push(lo);
    out.high.push(hi);
  }
  return out.idx.length > 0 ? out : null;
}

function factorNames(report: FactorReport, s: KalmanBetaSeries): string[] {
  const order = factorOrder(report).filter((name) => name in s.betas);
  return [...order, ...Object.keys(s.betas).filter((name) => !order.includes(name))];
}

/** Everything the panel draws, or null when no factor has a value after warm-up. Memoise per report. */
export function buildKalmanModel(report: FactorReport, s: KalmanBetaSeries): KalmanModel | null {
  const names = factorNames(report, s);
  const dense = names.flatMap((name) => {
    const d = densify(s, name);
    return d ? [d] : [];
  });
  if (dense.length === 0) return null;
  const extent = dense.map((d) => ({ min: Math.min(...d.low), max: Math.max(...d.high) }));
  const span = Math.max(Math.max(...extent.map((e) => e.max - e.min)) * SPAN_PADDING, 1e-9);
  const firstIdx = Math.min(...dense.map((d) => d.idx[0] as number));
  const first = s.dates[firstIdx] as string;
  const last = s.dates[s.dates.length - 1] as string;
  const from = isoMs(first);
  const to = Math.max(isoMs(last), from + 1);
  const x = (iso: string) => ((isoMs(iso) - from) / (to - from)) * 1000;

  const rows = dense.map((d, r): KalmanRowData => {
    const e = extent[r] as { min: number; max: number };
    const mid = (e.max + e.min) / 2;
    const lo = mid - span / 2;
    const hi = mid + span / 2;
    const y = (v: number) => ((hi - v) / span) * 100;
    const keep = thinIndices([d.beta, d.low, d.high]);
    const at = (k: number) => `${x(s.dates[d.idx[k] as number] as string).toFixed(2)} `;
    const walk = (values: number[]) =>
      keep.map((k, j) => `${j === 0 ? "M" : "L"}${at(k)}${y(values[k] as number).toFixed(2)}`).join("");
    const lower = [...keep]
      .reverse()
      .map((k) => `L${at(k)}${y(d.low[k] as number).toFixed(2)}`)
      .join("");
    return {
      name: d.name,
      plain: PLAIN[d.name] ?? "",
      slot: slotOf(d.name, names),
      latest: s.latest[d.name] ?? null,
      total: d.idx.length,
      drawn: keep.length,
      line: walk(d.beta),
      band: `${walk(d.high)}${lower}Z`,
      lo,
      hi,
      min: Math.min(...d.beta),
      max: Math.max(...d.beta),
    };
  });

  const cuts = s.vintages
    .slice(1)
    .map((v) => ((isoMs(v.valid_from) - from) / (to - from)) * 100)
    .filter((p) => p > 0.5 && p < 99.5);
  return { rows, first, last, from, to, cuts };
}

// ---------------------------------------------------------------------------- text

/** Three significant digits: 0.0736, 0.126, 0.226. */
function sd3(x: number | null | undefined): string {
  if (x == null) return "n/a";
  const s = Number(x.toPrecision(3));
  return num(s, Math.max(0, 2 - Math.floor(Math.log10(Math.abs(s) || 1))));
}

function bandText(l: KalmanLatest | null): string {
  return l ? `${num(l.band_low)} to ${num(l.band_high)}` : "n/a";
}

function windowText(v: KalmanVintage): string {
  return v.w_eq === null ? text.window_none : count(Math.round(v.w_eq));
}

/** The drift rate as a plain decimal to two significant digits (0.00000095). */
export function plainRate(x: number): string {
  if (!Number.isFinite(x)) return "n/a";
  if (x <= 0) return "0";
  return x.toFixed(Math.max(0, 1 - Math.floor(Math.log10(x))));
}

// ---------------------------------------------------------------------------- axis

/** Smallest distance in percent of the plot width between two x labels on a wide screen. */
const WIDE_GAP = 13;

/**
 * Indices of the x labels kept on a wide screen: the first and the last, then the major ones, then
 * the rest, each only when it clears every label already kept (a 3-year range has 12 quarterly ticks).
 */
export function spacedTicks(ticks: readonly { x: number; major: boolean }[], gap = WIDE_GAP): Set<number> {
  const rank = (i: number) => (i === 0 ? 0 : i === ticks.length - 1 ? 1 : ticks[i]?.major ? 2 : 3);
  const order = ticks.map((_, i) => i).sort((a, b) => rank(a) - rank(b) || a - b);
  const kept: number[] = [];
  for (const i of order) {
    const x = (ticks[i] as { x: number }).x;
    if (kept.every((k) => Math.abs((ticks[k] as { x: number }).x - x) >= gap)) kept.push(i);
  }
  return new Set(kept);
}

// ---------------------------------------------------------------------------- rows

function KalmanRow({ row, model }: { row: KalmanRowData; model: KalmanModel }) {
  const { lo, hi } = row;
  const span = hi - lo;
  const y = (v: number) => 100 - ((v - lo) / span) * 100;
  const labels: { value: number; kind: "top" | "bot" | "mid" }[] = [
    { value: hi, kind: "top" },
    { value: lo, kind: "bot" },
  ];
  const zeroInside = lo < 0 && hi > 0;
  if (zeroInside && Math.min(Math.abs(hi), Math.abs(lo)) > span * 0.34) labels.push({ value: 0, kind: "mid" });
  const l = row.latest;
  const summary =
    `${row.name} Kalman beta from ${dateLong(model.first)} to ${dateLong(model.last)}: ` +
    `lowest ${signed(row.min)}, highest ${signed(row.max)}`;

  return (
    <tr role="row" data-factor={row.name}>
      <th role="rowheader" scope="row">
        <span className="fname">
          <KeySwatch className={`cat c${row.slot}`} />
          {row.name}
        </span>
        {row.plain ? <span className="sub">{row.plain}</span> : null}
      </th>
      <td role="cell" className="plot-cell">
        <div className="plot mini">
          <svg
            className="line-svg kalman-svg"
            viewBox="0 0 1000 100"
            preserveAspectRatio="none"
            aria-hidden="true"
            data-testid={`kalman-chart-${row.name}`}
          >
            {zeroInside ? <line className="kalman-zero" x1="0" x2="1000" y1={y(0)} y2={y(0)} /> : null}
            {model.cuts.map((p) => (
              <line key={p} className="cutline" x1={p * 10} x2={p * 10} y1="0" y2="100" />
            ))}
            <path className={`band c${row.slot}`} d={row.band} />
            <path className={`rline c${row.slot}`} d={row.line} />
          </svg>
          <div className="ylabels" aria-hidden="true">
            {labels.map(({ value, kind }) => (
              <span key={kind} className={`yl ${kind}`} style={{ top: `${y(value).toFixed(2)}%` }}>
                {Math.abs(value) > 1e-9 ? signed(value, 2) : "0"}
              </span>
            ))}
          </div>
        </div>
        <span className="vh">{summary}</span>
      </td>
      <td role="cell" className="num strong">
        {l ? signed(l.beta) : "n/a"}
      </td>
      <td role="cell" className="num">
        {sd3(l?.sd)}
      </td>
      <td role="cell" className="num range">
        {bandText(l)}
      </td>
    </tr>
  );
}

function BetaTable({ model }: { model: KalmanModel }) {
  const span = model.to - model.from;
  const ticks = dateTicks(model.from, model.to);
  const pos = (ms: number) => ((ms - model.from) / Math.max(span, 1)) * 100;
  const placed = ticks.map((t) => ({ x: pos(t.ms), major: t.major }));
  const narrow = narrowTicks(placed);
  const wide = spacedTicks(placed);
  return (
    <table role="table" className="bars cols-3 rolling kalman-betas">
      <caption className="vh">{fill(text.table_caption, { last: dateLong(model.last) })}</caption>
      <thead role="rowgroup">
        <tr role="row">
          <th role="columnheader" scope="col">
            {text.beta_heads.factor}
          </th>
          <th role="columnheader" scope="col" className="plot-h">
            <span className="vh">{text.beta_heads.chart}</span>
          </th>
          <th role="columnheader" scope="col" className="num">
            {text.beta_heads.latest}
          </th>
          <th role="columnheader" scope="col" className="num" title={text.sd_title}>
            {text.beta_heads.sd}
          </th>
          <th role="columnheader" scope="col" className="num">
            {text.beta_heads.band}
          </th>
        </tr>
      </thead>
      <tbody role="rowgroup">
        {model.rows.map((row) => (
          <KalmanRow key={row.name} row={row} model={model} />
        ))}
      </tbody>
      <tfoot role="rowgroup">
        <tr role="row" className="axis-row" aria-hidden="true">
          <td role="cell" />
          <td role="cell" className="axis time">
            <div className="xl-wrap">
              {ticks.map((t, i) => {
                const x = pos(t.ms);
                return (
                  <span
                    key={t.ms}
                    className={`xl${t.major ? "" : " minor"}${narrow.has(i) ? " keep" : ""}${wide.has(i) ? " dk" : ""}${x < 3 ? " edge-l" : x > 97 ? " edge-r" : ""}`}
                    style={{ left: `${x.toFixed(2)}%` }}
                  >
                    {t.label}
                  </span>
                );
              })}
            </div>
          </td>
          <td role="cell" colSpan={3} />
        </tr>
      </tfoot>
    </table>
  );
}

const VINTAGE_HEADS = text.vintage_heads;

function VintageTable({ vintages }: { vintages: readonly KalmanVintage[] }) {
  const heads = VINTAGE_HEADS;
  return (
    <div className="kalman-vint">
      <h3 className="kalman-sub">{text.vintage_title}</h3>
      <table role="table" className="kalman-vt" aria-label={text.vintage_title}>
        <thead role="rowgroup">
          <tr role="row">
            {heads.map((h, i) => (
              <th key={h} role="columnheader" scope="col" className={i === 0 ? undefined : "num"}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody role="rowgroup">
          {vintages.map((v) => (
            <tr role="row" key={v.index}>
              <th role="rowheader" scope="row">
                {count(v.rows)}
              </th>
              <td role="cell" className="num" data-label={heads[1]}>
                {plainRate(v.lam)}
                {BOUND_WORDS[v.lam_at_bound] ? <span className="sub">{BOUND_WORDS[v.lam_at_bound]}</span> : null}
              </td>
              <td role="cell" className="num" data-label={heads[2]}>
                {windowText(v)}
              </td>
              <td role="cell" className="num" data-label={heads[3]}>
                {pct(v.resid_vol_ann, 1, false)}
              </td>
              <td role="cell" className="num" data-label={heads[4]}>
                <time dateTime={v.valid_from}>{dateLong(v.valid_from)}</time>
              </td>
              <td role="cell" className="num" data-label={heads[5]}>
                <time dateTime={v.valid_to}>{dateLong(v.valid_to)}</time>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------- panel

/** Panel 810: Kalman-filter betas. Five 56 px rows, numbers beside them, the yearly re-estimates below. */
export function KalmanPanel({ report }: ReportPanelProps) {
  const section = report.kalman_betas;
  const model = useMemo(
    () => (section && section.status === "ok" ? buildKalmanModel(report, section) : null),
    [report, section],
  );
  if (section === null) return null;

  if (section.status !== "ok") {
    return (
      <Panel
        id="kalman"
        title={TITLE}
        question={QUESTION}
        empty={{
          reason: section.reason ?? text.empty.not_computed,
          action: fill(section.status === "insufficient_data" ? text.empty.insufficient_data : text.empty.failed, {
            rows: section.training_rows,
          }),
        }}
      />
    );
  }
  if (!model) {
    return (
      <Panel
        id="kalman"
        title={TITLE}
        question={QUESTION}
        empty={{ reason: text.empty.warm_up_reason, action: text.empty.warm_up_step }}
      />
    );
  }

  const legend = (
    <ul className="legend" aria-label="Legend">
      <li>
        <svg className="sw" aria-hidden="true">
          <line className="total-line" x1="0" x2="14" y1="5" y2="5" />
        </svg>
        {text.legend[0]}
      </li>
      <li>
        <svg className="sw" aria-hidden="true">
          <rect className="kalman-band-sw" width="14" height="10" rx="2" />
        </svg>
        {text.legend[1]}
      </li>
      <li>
        <svg className="sw" aria-hidden="true">
          <line className="cutline" x1="7" x2="7" y1="0" y2="10" />
        </svg>
        {text.legend[2]}
      </li>
    </ul>
  );

  const how = [
    ...labelTexts(
      report,
      section.labels.filter((k) => k !== "L-KTAIL"),
    ),
    text.fold.span,
    text.fold.thinning,
    text.fold.drift_rate,
    ...labelTexts(
      report,
      section.labels.filter((k) => k === "L-KTAIL"),
    ),
    ...section.warnings.map((code) => WARNING_TEXT[code] ?? code),
  ].join(" ");

  return (
    <Panel
      id="kalman"
      title={TITLE}
      question={QUESTION}
      legend={legend}
      reading={text.reading}
      footnote={fill(text.footnote, {
        first: dateLong(model.first),
        last: dateLong(model.last),
        rows: count(section.training_rows),
      })}
      how={how}
    >
      <BetaTable model={model} />
      {section.vintages.length > 0 ? <VintageTable vintages={section.vintages} /> : null}
    </Panel>
  );
}
