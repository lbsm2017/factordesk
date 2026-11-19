/* eslint-disable jsx-a11y/no-redundant-roles, jsx-a11y/no-interactive-element-to-noninteractive-role --
   DB7 asks for explicit table roles: the narrow-screen CSS restyles rows as grids, which can drop table semantics. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FactorReport, RollingWindow } from "../../api/types";
import { dateLong, signed } from "../../format";
import {
  DEFAULT_Z,
  type BetaStats,
  dateTicks,
  describe,
  factorOrder,
  finite,
  firstFullWindow,
  isoMs,
  labelTexts,
  rollingPoints,
  slotOf,
  windowStats,
} from "../../report/derive";
import type { RollingWindowDays } from "../../state/url";
import { rollingOutcome } from "../../text/outcome";
import { PLAIN } from "../../text/plain";
import { type ChartTokens, useChartTokens } from "../charts/chartTokens";
import type { ECharts, EChartsCoreOption } from "../charts/echartsCore";
import { useEChart } from "../charts/useEChart";
import { KeySwatch, numN, signedN } from "./barParts";
import { EmptyState } from "./EmptyState";
import { Panel } from "./Panel";
import type { ReportPanelProps } from "./types";
import "./rolling.css";

export interface RollingPanelProps extends ReportPanelProps {
  /** Window shown. ReportView passes `win ?? report.average_beta.window`. */
  win: RollingWindowDays;
  /** Commit a window change (App writes `win` to the URL). */
  onWinChange: (win: RollingWindowDays) => void;
}

/** Charts in this group share zoom and the hover line (`echarts.connect`). */
export const ROLLING_GROUP = "rolling-betas";

const SPAN_PADDING = 1.08;
const MIN_ZOOM_SPAN_MS = 30 * 86_400_000;

// ---------------------------------------------------------------------------- series

export interface RollingRowData {
  name: string;
  plain: string;
  slot: 1 | 2 | 3 | 4 | 5;
  /** Stamp times in ms and values; warm-up stamps are left out. */
  ms: number[];
  beta: number[];
  lower: number[];
  upper: number[];
  /** Vertical span of this row: the common span, centred on the row's own values. */
  lo: number;
  hi: number;
  stats: BetaStats;
}

export interface RollingBlockData {
  window: number;
  z: number;
  rows: RollingRowData[];
  /** First and last stamp shown, in ms. */
  from: number;
  to: number;
  firstFull: string;
  lastDate: string;
}

/** Prepare every row of one window; null when every estimate is still in warm-up. */
export function buildRollingBlock(report: FactorReport, w: RollingWindow): RollingBlockData | null {
  const order = factorOrder(report);
  const z = finite(w.ci_z) ?? DEFAULT_Z;
  const prepared = order.flatMap((name) => {
    const pts = rollingPoints(w, name);
    const stats = windowStats(report, w, name);
    if (pts.length === 0 || !stats) return [];
    return [{ name, pts, stats }];
  });
  if (prepared.length === 0) return null;
  const extent = prepared.map(({ pts }) => {
    const ups = pts.map((p) => p.beta + z * p.se);
    const downs = pts.map((p) => p.beta - z * p.se);
    return { max: Math.max(...ups), min: Math.min(...downs) };
  });
  const span = Math.max(Math.max(...extent.map((e) => e.max - e.min)) * SPAN_PADDING, 1e-9);
  const rows = prepared.map(({ name, pts, stats }, i): RollingRowData => {
    const e = extent[i] as { max: number; min: number };
    const mid = (e.max + e.min) / 2;
    return {
      name,
      plain: PLAIN[name] ?? "",
      slot: slotOf(name, order),
      ms: pts.map((p) => isoMs(w.dates[p.index] as string)),
      beta: pts.map((p) => p.beta),
      lower: pts.map((p) => p.beta - z * p.se),
      upper: pts.map((p) => p.beta + z * p.se),
      lo: mid - span / 2,
      hi: mid + span / 2,
      stats,
    };
  });
  const firstFull = firstFullWindow(w, order) as string;
  const lastDate = w.dates[w.dates.length - 1] as string;
  return { window: w.window, z, rows, from: isoMs(firstFull), to: Math.max(isoMs(lastDate), isoMs(firstFull) + 1), firstFull, lastDate };
}

// ---------------------------------------------------------------------------- chart option

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);
}

function isoOf(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

/** ECharts option of one row: line over a stacked band, common span, connected hover line. */
export function buildRowOption(block: RollingBlockData, row: RollingRowData, tokens: ChartTokens): EChartsCoreOption {
  const color = tokens.factors[row.slot - 1];
  const dated = (values: number[]) => row.ms.map((t, i) => [t, values[i]]);
  const width = row.upper.map((u, i) => u - (row.lower[i] as number));
  const januaries = dateTicks(block.from, block.to)
    .filter((t) => t.january)
    .map((t) => ({ xAxis: t.ms }));
  const guides: object[] = januaries.map((d) => ({ ...d, lineStyle: { color: tokens.grid, width: 1, type: "solid" } }));
  if (row.lo < 0 && row.hi > 0) guides.push({ yAxis: 0, lineStyle: { color: tokens.axis, width: 1, type: "solid" } });
  const none = { show: false };
  return {
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: {
      type: "time",
      min: block.from,
      max: block.to,
      axisLine: none,
      axisTick: none,
      axisLabel: none,
      splitLine: none,
    },
    yAxis: { type: "value", min: row.lo, max: row.hi, axisLine: none, axisTick: none, axisLabel: none, splitLine: none },
    dataZoom: [
      {
        type: "inside",
        xAxisIndex: 0,
        startValue: block.from,
        endValue: block.to,
        filterMode: "none",
        zoomOnMouseWheel: "ctrl",
        moveOnMouseMove: true,
        moveOnMouseWheel: false,
        preventDefaultMouseMove: false,
        minValueSpan: MIN_ZOOM_SPAN_MS,
      },
    ],
    tooltip: {
      trigger: "axis",
      confine: true,
      transitionDuration: 0,
      backgroundColor: tokens.surface,
      borderColor: tokens.axis,
      borderWidth: 1,
      padding: [2, 6],
      textStyle: { color: tokens.ink, fontFamily: tokens.sans, fontSize: 12 },
      extraCssText: "box-shadow:none;",
      axisPointer: { type: "line", lineStyle: { color: tokens.ink3, width: 1 } },
      position: (point: number[], _p: unknown, _d: unknown, _r: unknown, size: { contentSize: number[]; viewSize: number[] }) => [
        point[0]! > size.viewSize[0]! / 2 ? point[0]! - size.contentSize[0]! - 10 : point[0]! + 10,
        2,
      ],
      formatter: (params: { dataIndex?: number } | { dataIndex?: number }[]) => {
        const first = Array.isArray(params) ? params[0] : params;
        const i = first?.dataIndex;
        if (i === undefined || row.ms[i] === undefined) return "";
        const iso = isoOf(row.ms[i]);
        return escapeHtml(
          `${dateLong(iso)}  ${signed(row.beta[i] as number)} (${signed(row.lower[i] as number, 2)} to ${signed(row.upper[i] as number, 2)})`,
        );
      },
    },
    series: [
      {
        type: "line",
        name: "lower",
        data: dated(row.lower),
        stack: "band",
        stackStrategy: "all",
        symbol: "none",
        silent: true,
        lineStyle: { opacity: 0 },
        tooltip: { show: false },
        markLine: { silent: true, symbol: "none", label: none, animation: false, z: 0, data: guides },
      },
      {
        type: "line",
        name: "band",
        data: dated(width),
        stack: "band",
        stackStrategy: "all",
        symbol: "none",
        silent: true,
        lineStyle: { opacity: 0 },
        areaStyle: { color, opacity: 0.16 },
        tooltip: { show: false },
      },
      {
        type: "line",
        name: "beta",
        data: dated(row.beta),
        symbol: "none",
        showSymbol: false,
        lineStyle: { color, width: 1.75 },
        itemStyle: { color },
        emphasis: { disabled: true },
      },
    ],
  };
}

// ---------------------------------------------------------------------------- one row

interface RowProps {
  block: RollingBlockData;
  row: RollingRowData;
  tokens: ChartTokens;
  /** Register the chart instance (for the reset button). */
  onChart: (name: string, chart: ECharts | null) => void;
  /** Called with the visible time range after a zoom; only the first row reports. */
  onZoom?: ((from: number, to: number) => void) | undefined;
}

function RollingRow({ block, row, tokens, onChart, onZoom }: RowProps) {
  const ref = useRef<HTMLDivElement>(null);
  const option = useMemo(() => buildRowOption(block, row, tokens), [block, row, tokens]);
  const chart = useEChart(ref, option, { group: ROLLING_GROUP });

  useEffect(() => {
    onChart(row.name, chart);
    return () => onChart(row.name, null);
  }, [chart, onChart, row.name]);

  useEffect(() => {
    if (!chart || !onZoom) return;
    const handler = () => {
      const zoom = (chart.getOption() as { dataZoom?: { startValue?: number; endValue?: number }[] }).dataZoom?.[0];
      if (zoom?.startValue !== undefined && zoom.endValue !== undefined) onZoom(zoom.startValue, zoom.endValue);
    };
    chart.on("datazoom", handler);
    return () => {
      chart.off("datazoom", handler);
    };
  }, [chart, onZoom]);

  const { lo, hi } = row;
  const span = hi - lo;
  const y = (v: number) => 100 - ((v - lo) / span) * 100;
  const labels: { value: number; kind: "top" | "bot" | "mid" }[] = [
    { value: hi, kind: "top" },
    { value: lo, kind: "bot" },
  ];
  if (lo < 0 && hi > 0 && Math.min(Math.abs(hi), Math.abs(lo)) > span * 0.22) labels.push({ value: 0, kind: "mid" });

  const s = row.stats;
  const tip =
    `Spread ${numN(s.sd)}, lowest ${signedN(s.min)}, highest ${signedN(s.max)}, ` +
    `above zero in ${Math.round(s.shareAbove * 100)}% of windows`;

  return (
    <tr role="row">
      <th role="rowheader" scope="row">
        <span className="fname">
          <KeySwatch className={`cat c${row.slot}`} />
          {row.name}
        </span>
        {row.plain ? <span className="sub">{row.plain}</span> : null}
      </th>
      <td role="cell" className="plot-cell">
        <div className="plot mini">
          <div ref={ref} className="rolling-chart" aria-hidden="true" data-testid={`rolling-chart-${row.name}`} />
          <div className="ylabels" aria-hidden="true">
            {labels.map(({ value, kind }) => (
              <span key={kind} className={`yl ${kind}`} style={{ top: `${y(value).toFixed(2)}%` }}>
                {Math.abs(value) > 1e-9 ? signed(value, 2) : "0"}
              </span>
            ))}
          </div>
        </div>
      </td>
      <td role="cell" className="num strong">
        {signed(s.latest)}
      </td>
      <td role="cell" className="num">
        {signed(s.mean)}
      </td>
      <td role="cell" className="num range" title={tip}>
        {`${signed(s.p10, 2)} to ${signed(s.p90, 2)}`}
        <span className="vh">. {tip}</span>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------- one window

/** Plot width in percent that one label needs on a phone ("Jan 2026" in a plot about 300 px wide). */
const NARROW_GAP = 24;

/**
 * Indices of the x labels kept under 720 px: the first and the last always, then the major ones
 * that clear every label already kept. Fixes a phone showing a single label (review DF8).
 */
export function narrowTicks(ticks: { x: number; major: boolean }[]): Set<number> {
  const rank = (i: number) => (i === 0 ? 0 : i === ticks.length - 1 ? 1 : ticks[i]?.major ? 2 : 3);
  const order = ticks.map((_, i) => i).filter((i) => rank(i) < 3);
  order.sort((a, b) => rank(a) - rank(b) || a - b);
  const kept: number[] = [];
  for (const i of order) {
    const x = (ticks[i] as { x: number }).x;
    if (kept.every((k) => Math.abs((ticks[k] as { x: number }).x - x) >= NARROW_GAP)) kept.push(i);
  }
  return new Set(kept);
}

function RollingBlock({
  block,
  tokens,
  onReady,
}: {
  block: RollingBlockData;
  tokens: ChartTokens;
  onReady: (reset: (() => void) | null) => void;
}) {
  const charts = useRef(new Map<string, ECharts>());
  const [view, setView] = useState<{ window: number; from: number; to: number } | null>(null);
  const visible = view && view.window === block.window ? view : null;
  const from = visible?.from ?? block.from;
  const to = visible?.to ?? block.to;
  const zoomed = visible !== null && (visible.from > block.from + 1 || visible.to < block.to - 1);

  const onChart = useCallback((name: string, chart: ECharts | null) => {
    if (chart) charts.current.set(name, chart);
    else charts.current.delete(name);
  }, []);
  const days = block.window;
  const onZoom = useCallback((a: number, b: number) => setView({ window: days, from: a, to: b }), [days]);

  const reset = useCallback(() => {
    for (const chart of charts.current.values()) {
      if (chart.isDisposed()) continue;
      chart.dispatchAction({ type: "dataZoom", startValue: block.from, endValue: block.to, escapeConnect: true });
    }
    setView(null);
  }, [block.from, block.to]);

  useEffect(() => {
    onReady(zoomed ? reset : null);
    return () => onReady(null);
  }, [onReady, reset, zoomed]);

  const ticks = dateTicks(from, to);
  const pos = (ms: number) => ((ms - from) / Math.max(to - from, 1)) * 100;
  const narrow = narrowTicks(ticks.map((t) => ({ x: pos(t.ms), major: t.major })));
  const k = block.window;

  return (
    <div className={`win w-${k}`}>
      <table role="table" className="bars cols-3 rolling">
        <caption className="vh">
          Rolling {k}-day betas per factor with a pointwise 95% band; latest, average and middle 80% of the estimates
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
              Latest
            </th>
            <th role="columnheader" scope="col" className="num">
              Average
            </th>
            <th role="columnheader" scope="col" className="num">
              Middle 80%
            </th>
          </tr>
        </thead>
        <tbody role="rowgroup">
          {block.rows.map((row, i) => (
            <RollingRow
              key={row.name}
              block={block}
              row={row}
              tokens={tokens}
              onChart={onChart}
              onZoom={i === 0 ? onZoom : undefined}
            />
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
      <p className="foot">
        Each point uses the previous {k} trading days, so the chart starts at the first full window,{" "}
        {dateLong(block.firstFull)}. Latest is stamped {dateLong(block.lastDate)}.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------- panel

const WINDOW_ACTION = "Choose an earlier start date or the shorter window.";

/** Panel 8: exposure over time. Five 56 px rows, connected charts, window radios. */
export function RollingPanel({ report, win, onWinChange }: RollingPanelProps) {
  const tokens = useChartTokens();
  const [reset, setReset] = useState<(() => void) | null>(null);
  const onReady = useCallback((fn: (() => void) | null) => setReset(() => fn), []);

  const title = "Exposure over time";
  const question = "Have the exposures been stable, or did they drift?";
  const windows = useMemo(() => [...report.rolling].sort((a, b) => a.window - b.window), [report.rolling]);
  const usable = windows.filter((w) => w.status === "ok" && w.dates.length > 0);
  const order = factorOrder(report);

  const selected = windows.find((w) => w.window === win);
  const block = useMemo(
    () => (selected && selected.status === "ok" && selected.dates.length > 0 ? buildRollingBlock(report, selected) : null),
    [report, selected],
  );

  if (usable.length === 0 || order.length === 0) {
    const reason = windows.find((w) => w.reason)?.reason;
    return (
      <Panel
        id="rolling"
        title={title}
        question={question}
        empty={{
          reason: reason ?? "Insufficient data: no rolling-beta series.",
          action: "Rolling betas need more trading days than the window length. Choose an earlier start date.",
        }}
      />
    );
  }

  const toggle = (
    <div className="rolling-ctl">
      {reset ? (
        <button type="button" className="chip zoom-reset" onClick={reset}>
          Show full range
        </button>
      ) : null}
      <div className="seg" role="group" aria-label="Rolling window length">
        <span className="seg-lab" aria-hidden="true">
          Window
        </span>
        <span className="seg-btns">
          {windows.map((w) => (
            <RadioLabel key={w.window} days={w.window} checked={w.window === win} onSelect={onWinChange} />
          ))}
        </span>
      </div>
    </div>
  );

  const desc = describe(report);
  const caption = usable.find((w) => w.caption)?.caption;
  const how = [
    caption,
    "Every row uses the same vertical span, centred on its own values, so wiggles compare across factors.",
    "Hold Ctrl and scroll, or pinch, to zoom the time axis; the rows zoom together.",
    ...labelTexts(report, usable[0]?.labels ?? []),
  ]
    .filter(Boolean)
    .join(" ");

  let body;
  if (!selected) {
    body = <EmptyState reason={`The ${win}-day window is not in this report.`} action={WINDOW_ACTION} />;
  } else if (selected.status !== "ok" || selected.dates.length === 0) {
    body = (
      <div className={`win w-${selected.window}`}>
        <EmptyState
          reason={selected.reason ?? `The ${selected.window}-day window could not be computed.`}
          action={WINDOW_ACTION}
        />
      </div>
    );
  } else if (!block) {
    body = (
      <EmptyState
        reason={`Insufficient data: every ${selected.window}-day estimate is still in warm-up (no full window).`}
        action={WINDOW_ACTION}
      />
    );
  } else {
    body = <RollingBlock block={block} tokens={tokens} onReady={onReady} />;
  }

  return (
    <Panel
      id="rolling"
      title={title}
      question={question}
      outcome={rollingOutcome(report, win)}
      legend={toggle}
      footnote={`${desc} The band is a pointwise 95% interval.`}
      how={how}
    >
      {body}
    </Panel>
  );
}

function RadioLabel({
  days,
  checked,
  onSelect,
}: {
  days: number;
  checked: boolean;
  onSelect: (win: RollingWindowDays) => void;
}) {
  const id = `win-${days}`;
  return (
    <>
      <input
        type="radio"
        name="rolling-window"
        id={id}
        value={days}
        checked={checked}
        onChange={() => {
          if (days === 126 || days === 252) onSelect(days);
        }}
      />
      <label htmlFor={id}>{days} days</label>
    </>
  );
}
