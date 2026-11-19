/**
 * Pure values for the price panel (design D4), ported from `_price_panel` in render_html.py:
 * which days are analysed, where the two cuts are, the side table, and the ECharts option.
 */
import type { FactorReport } from "../../api/types";
import { dateLong, num, pct } from "../../format";
import { isMonthly } from "../../report/subject";
import { CHART_FONT_PX } from "../charts/chartTokens";
import type { ChartTokens } from "../charts/chartTokens";
import type { EChartsCoreOption } from "../charts/echartsCore";

const DAY_MS = 86_400_000;

export interface PricePoint {
  /** ISO date. */
  date: string;
  /** Midnight UTC of the date, in milliseconds. */
  ms: number;
  value: number;
}

export interface SideRow {
  label: string;
  /** Date, or the sentence under the label. */
  sub: string;
  value: string;
  muted: boolean;
}

export interface PriceModel {
  points: PricePoint[];
  /** Index of the last point on or before the end of the factor data; -1 when none is. */
  cut: number;
  /** Index where the analysed days start, when that cut is marked (at least two earlier days); else null. */
  startCut: number | null;
  /** The right cut is marked: there are days after the end of the factor data, or no day is covered. */
  endCut: boolean;
  /** Label of the right band. Present exactly when `endCut` is true. */
  endLabel: string | null;
  /** Label of the left band. Present exactly when `startCut` is not null. */
  startLabel: string | null;
  rows: SideRow[];
  /** Zoom window on load: from 10% of the analysed span before the first analysed day, to the last price. */
  initialStartMs: number;
  /** True when the loaded window starts after the first price, so a "Show full history" button has an effect. */
  canShowFull: boolean;
}

export function toMs(isoDate: string): number {
  return Date.parse(`${isoDate}T00:00:00Z`);
}

/** The price points that can be drawn, or null when fewer than two exist. */
export function priceModel(report: FactorReport): PriceModel | null {
  const { price_series: ps, data: d } = report;
  const points: PricePoint[] = [];
  ps.dates.forEach((date, i) => {
    const value = ps.adj_close[i];
    const ms = toMs(date);
    if (typeof value === "number" && Number.isFinite(value) && Number.isFinite(ms)) points.push({ date, ms, value });
  });
  const first = points[0];
  const last = points[points.length - 1];
  if (!first || !last || points.length < 2) return null;

  const cov = ps.factor_coverage_end;
  let cut = -1;
  points.forEach((p, k) => {
    if (p.date <= cov) cut = k;
  });
  let startK = points.findIndex((p) => p.date >= d.actual_start);
  if (startK < 0) startK = 0;

  const endCut = cut === -1 || cut < points.length - 1;
  // One earlier day is only the base price of the first return, so it is not marked.
  const startCut = cut >= 0 && startK >= 2 && startK <= cut ? startK : null;
  const startPoint = startCut === null ? null : points[startCut];

  const rows: SideRow[] = [{ label: "First", sub: dateLong(first.date), value: num(first.value, 2), muted: false }];
  const atCut = cut >= 0 ? points[cut] : undefined;
  if (atCut) {
    rows.push({ label: "End of factor data", sub: dateLong(atCut.date), value: num(atCut.value, 2), muted: false });
  }
  rows.push({ label: "Latest", sub: dateLong(last.date), value: num(last.value, 2), muted: false });
  const u = d.uncovered;
  if (u.n > 0 && typeof u.compounded_return === "number" && Number.isFinite(u.compounded_return)) {
    rows.push({
      label: "After factor data",
      sub: `${u.n} ${isMonthly(report) ? (u.n === 1 ? "month" : "months") : u.n === 1 ? "day" : "days"}, raw, not analysed`,
      value: pct(u.compounded_return),
      muted: true,
    });
  }

  const span = Math.max(toMs(d.actual_end) - toMs(d.actual_start), 0);
  const wanted = toMs(d.actual_start) - 0.1 * span;
  const initialStartMs = Number.isFinite(wanted) ? Math.min(Math.max(wanted, first.ms), last.ms) : first.ms;

  return {
    points,
    cut,
    startCut,
    endCut,
    endLabel: endCut ? `Not analysed: factor data ends ${dateLong(cov)}` : null,
    startLabel: startPoint ? `Not analysed: before ${dateLong(startPoint.date)}` : null,
    rows,
    initialStartMs,
    canShowFull: initialStartMs > first.ms + DAY_MS / 2,
  };
}

/** Which of the two "Not analysed" labels belong to the visible part of the time axis. */
export function visibleLabels(
  model: PriceModel,
  view: { start: number; end: number },
): { start: string | null; end: string | null } {
  const startPoint = model.startCut === null ? undefined : model.points[model.startCut];
  const endPoint = model.cut >= 0 ? model.points[model.cut] : undefined;
  return {
    // The left band is visible while the view starts before its cut rule.
    start: startPoint && view.start < startPoint.ms ? model.startLabel : null,
    // The right band is visible while the view ends after its cut rule (always when no day is covered).
    end: model.endLabel !== null && (!endPoint || view.end > endPoint.ms) ? model.endLabel : null,
  };
}

const HTML_ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => HTML_ESCAPES[c] ?? c);
}

function priceLabel(v: number): string {
  return num(v, Number.isInteger(v) ? 0 : 2);
}

function isoOf(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

/** Tooltip body: the date and the price. Every string is escaped. */
export function tooltipHtml(ms: number, value: number): string {
  return `${escapeHtml(dateLong(isoOf(ms)))}<br/><b>${escapeHtml(num(value, 2))}</b>`;
}

export interface PriceOptionArgs {
  /** Show the whole history instead of the loaded window. */
  full: boolean;
}

/** ECharts option: true time axis, ink line, two grid bands with dashed cut rules, inside zoom. */
export function priceOption(model: PriceModel, tokens: ChartTokens, { full }: PriceOptionArgs): EChartsCoreOption {
  const { points, cut } = model;
  const first = points[0];
  const last = points[points.length - 1];
  if (!first || !last) return {};
  const xy = (p: PricePoint): [number, number] => [p.ms, p.value];
  const covered = points.slice(0, cut + 1).map(xy);
  const tail = points.slice(Math.max(cut, 0)).map(xy);

  const bands: [{ xAxis: number }, { xAxis: number }][] = [];
  const rules: { xAxis: number }[] = [];
  const startPoint = model.startCut === null ? undefined : points[model.startCut];
  const endPoint = cut >= 0 ? points[cut] : undefined;
  if (startPoint) {
    bands.push([{ xAxis: first.ms }, { xAxis: startPoint.ms }]);
    rules.push({ xAxis: startPoint.ms });
  }
  if (model.endCut) {
    bands.push([{ xAxis: endPoint ? endPoint.ms : first.ms }, { xAxis: last.ms }]);
    if (endPoint) rules.push({ xAxis: endPoint.ms });
  }

  const label = { color: tokens.ink3, fontFamily: tokens.sans, fontSize: CHART_FONT_PX };
  return {
    useUTC: true,
    textStyle: { fontFamily: tokens.sans, fontSize: CHART_FONT_PX },
    grid: { left: 58, right: 10, top: 10, bottom: 36 },
    tooltip: {
      trigger: "axis",
      confine: true,
      backgroundColor: tokens.surface,
      borderColor: tokens.axis,
      borderWidth: 1,
      padding: [6, 10],
      textStyle: { color: tokens.ink, fontFamily: tokens.sans, fontSize: CHART_FONT_PX },
      axisPointer: { type: "line", lineStyle: { color: tokens.ink3, width: 1 } },
      formatter: (params: unknown) => {
        const first = Array.isArray(params) ? (params[0] as { value?: unknown } | undefined) : undefined;
        const v = first?.value;
        if (!Array.isArray(v) || typeof v[0] !== "number" || typeof v[1] !== "number") return "";
        return tooltipHtml(v[0], v[1]);
      },
    },
    xAxis: {
      type: "time",
      min: first.ms,
      max: last.ms,
      axisLine: { lineStyle: { color: tokens.axis } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: {
        ...label,
        margin: 10,
        hideOverlap: true,
        formatter: { year: "{yyyy}", month: "{MMM}", day: "{d} {MMM}" },
      },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      splitNumber: 2,
      splitLine: { lineStyle: { color: tokens.grid, width: 1 } },
      axisLabel: { ...label, margin: 8, formatter: (v: number) => priceLabel(v) },
    },
    dataZoom: [
      {
        type: "inside",
        xAxisIndex: 0,
        filterMode: "filter",
        startValue: full ? first.ms : model.initialStartMs,
        endValue: last.ms,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        preventDefaultMouseMove: false,
      },
    ],
    series: [
      {
        // Hosts the bands and cut rules below the price lines; drawn invisible.
        name: "bands",
        type: "line",
        z: 1,
        silent: true,
        symbol: "none",
        lineStyle: { opacity: 0 },
        tooltip: { show: false },
        data: points.map(xy),
        markArea: {
          silent: true,
          animation: false,
          itemStyle: { color: tokens.grid, opacity: 1 },
          data: bands,
        },
        markLine: {
          silent: true,
          animation: false,
          symbol: "none",
          label: { show: false },
          lineStyle: { color: tokens.ink3, width: 1, type: [3, 3] },
          data: rules,
        },
      },
      {
        name: "Adjusted close",
        type: "line",
        z: 3,
        symbol: "none",
        showSymbol: false,
        lineStyle: { color: tokens.ink, width: 1.5, join: "round", cap: "round" },
        itemStyle: { color: tokens.ink },
        emphasis: { disabled: true },
        data: covered,
      },
      {
        name: "After factor data",
        type: "line",
        z: 3,
        symbol: "none",
        showSymbol: false,
        lineStyle: { color: tokens.ink3, width: 1.5, join: "round", cap: "round" },
        itemStyle: { color: tokens.ink3 },
        emphasis: { disabled: true },
        data: tail,
      },
    ],
  };
}
