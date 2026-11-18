/* eslint-disable jsx-a11y/no-redundant-roles, jsx-a11y/no-interactive-element-to-noninteractive-role --
   DB7 asks for explicit table roles: the narrow-screen CSS restyles rows as grids, which can drop table semantics. */
import { useMemo } from "react";
import type { FactorReport, KalmanBetaSeries } from "../../../api/types";
import type { components } from "../../../api/types.gen";
import { count, dateLong, num, pct, signed } from "../../../format";
import { dateTicks, factorOrder, finite, isoMs, labelTexts, sci, slotOf } from "../../../report/derive";
import { PLAIN } from "../../../text/plain";
import { KeySwatch } from "../barParts";
import { Panel } from "../Panel";
import { narrowTicks } from "../RollingPanel";
import type { ReportPanelProps } from "../types";
import "./KalmanPanel.css";

type KalmanVintage = components["schemas"]["KalmanVintage"];
type KalmanLatest = components["schemas"]["KalmanLatest"];

const TITLE = "Kalman-filter betas";
const QUESTION = "How did the exposures move, using only data up to each date?";

/** Same padding on the common vertical span as the rolling panel. */
const SPAN_PADDING = 1.08;
/** A series up to this many points is drawn as it is; a longer one is thinned. */
export const MAX_DRAWN_POINTS = 1500;
/** Buckets used when thinning: each keeps its first and last point and its extremes. */
export const THIN_BUCKETS = 300;

/** Sentences for the warning codes of the section (backend `WARNING_TEXT`). */
const WARNING_TEXT: Record<string, string> = {
  kalman_lambda_at_upper_bound:
    "For at least one yearly re-estimate the filter follows daily noise; the estimate is not meaningful.",
};

const BOUND_WORDS: Record<KalmanVintage["lam_at_bound"], string> = {
  zero: "At zero: no drift detected, so the filter uses all data so far.",
  upper: "At the upper limit: the filter follows daily noise; the estimate is not meaningful.",
  none: "Within limits.",
};

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
  slot: 1 | 2 | 3 | 4 | 5;
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
  return v.w_eq === null ? "All data so far" : `${count(Math.round(v.w_eq))} days`;
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
  if (zeroInside && Math.min(Math.abs(hi), Math.abs(lo)) > span * 0.22) labels.push({ value: 0, kind: "mid" });
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
  const narrow = narrowTicks(ticks.map((t) => ({ x: pos(t.ms), major: t.major })));
  return (
    <table role="table" className="bars cols-3 rolling kalman-betas">
      <caption className="vh">
        Kalman-filter beta per factor with a model-based 95% band, latest at {dateLong(model.last)}: latest beta, standard
        deviation, and the band from low to high
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
            Latest beta
          </th>
          <th role="columnheader" scope="col" className="num">
            sd
          </th>
          <th role="columnheader" scope="col" className="num">
            Band low to high
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
                    className={`xl${t.major ? "" : " minor"}${narrow.has(i) ? " keep" : ""}${x < 3 ? " edge-l" : x > 97 ? " edge-r" : ""}`}
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

const VINTAGE_HEADS = [
  "Rows used",
  "Drift rate (lambda)",
  "Behaves like a window of",
  "Residual volatility a year",
  "Valid from",
  "Valid to",
  "Limit",
] as const;

function VintageTable({ vintages }: { vintages: readonly KalmanVintage[] }) {
  const heads = VINTAGE_HEADS;
  return (
    <div className="kalman-vint">
      <h3 className="kalman-sub">Yearly re-estimates of the drift rate</h3>
      <table role="table" className="kalman-vt" aria-label="Yearly re-estimates of the drift rate">
        <thead role="rowgroup">
          <tr role="row">
            {heads.map((h, i) => (
              <th key={h} role="columnheader" scope="col" className={i === 0 || i === heads.length - 1 ? undefined : "num"}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody role="rowgroup">
          {vintages.map((v) => (
            <tr role="row" key={v.index} className={v.lam_at_bound === "none" ? undefined : "bound"}>
              <th role="rowheader" scope="row">
                {count(v.rows)} rows
              </th>
              <td role="cell" className="num" data-label={heads[1]}>
                {sci(v.lam)}
              </td>
              <td role="cell" className="num" data-label={heads[2]}>
                {windowText(v)}
              </td>
              <td role="cell" className="num" data-label={heads[3]}>
                {pct(v.resid_vol_ann, 1, false)}
              </td>
              <td role="cell" className="num" data-label={heads[4]}>
                {v.valid_from}
              </td>
              <td role="cell" className="num" data-label={heads[5]}>
                {v.valid_to}
              </td>
              <td role="cell" className="lim" data-label={heads[6]}>
                {BOUND_WORDS[v.lam_at_bound]}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------- panel

const EMPTY_ACTION = "Choose an earlier start date; the filter needs at least 504 trading days.";

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
          reason: section.reason ?? "Insufficient data: the Kalman-filter betas could not be computed.",
          action: EMPTY_ACTION,
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
        empty={{
          reason: "Insufficient data: every Kalman-filter estimate is still in warm-up (no value yet).",
          action: EMPTY_ACTION,
        }}
      />
    );
  }

  const legend = (
    <ul className="legend" aria-label="Legend">
      <li>
        <svg className="sw" aria-hidden="true">
          <line className="total-line" x1="0" x2="14" y1="5" y2="5" />
        </svg>
        Kalman-filter beta
      </li>
      <li>
        <svg className="sw" aria-hidden="true">
          <rect className="kalman-band-sw" width="14" height="10" rx="2" />
        </svg>
        Model-based 95% band
      </li>
      <li>
        <svg className="sw" aria-hidden="true">
          <line className="cutline" x1="7" x2="7" y1="0" y2="10" />
        </svg>
        Yearly re-estimate
      </li>
    </ul>
  );

  const how = [
    "Every row uses the same vertical span, centred on its own band, so wiggles compare across factors.",
    "The chart draws a thinned copy of the daily series that keeps every high and low; the numbers use all of it.",
    ...labelTexts(report, section.labels),
    ...section.warnings.map((code) => WARNING_TEXT[code] ?? code),
  ].join(" ");

  return (
    <Panel
      id="kalman"
      title={TITLE}
      question={QUESTION}
      legend={legend}
      reading="Each day's estimate combines the previous day's estimate with that day's return, so every point uses only data up to its date. Compare the lines with the rolling betas."
      footnote={`The chart starts at ${dateLong(model.first)}, the first date with ${count(section.training_rows)} trading days of history. Latest is stamped ${dateLong(model.last)}. The band is a model-based 95% interval, not a Newey-West (HAC) interval.`}
      how={how}
    >
      <BetaTable model={model} />
      {section.vintages.length > 0 ? <VintageTable vintages={section.vintages} /> : null}
    </Panel>
  );
}
