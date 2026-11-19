import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { dateLong } from "../../format";
import { cloneReport, mockReport } from "../../test/fixture";
import type { ChartTokens } from "../charts/chartTokens";
import { PricePanel } from "./PricePanel";
import { escapeHtml, priceModel, priceOption, toMs, tooltipHtml, visibleLabels } from "./priceModel";

const fake = vi.hoisted(() => {
  const handlers = new Map<string, () => void>();
  const chart = {
    on: vi.fn((name: string, fn: () => void) => handlers.set(name, fn)),
    off: vi.fn((name: string) => handlers.delete(name)),
    isDisposed: () => false,
    getOption: vi.fn(() => ({ dataZoom: [{ startValue: 0, endValue: 0 }] })),
  };
  return { chart, handlers, option: null as Record<string, unknown> | null };
});

vi.mock("../charts/useEChart", () => ({
  useEChart: (_ref: unknown, option: Record<string, unknown> | null) => {
    fake.option = option;
    return fake.chart;
  },
}));

const tokens: ChartTokens = {
  surface: "s",
  sunk: "u",
  grid: "GRID",
  axis: "AXIS",
  ink: "INK",
  ink2: "INK2",
  ink3: "INK3",
  pos: "p",
  neg: "n",
  factors: ["1", "2", "3", "4", "5", "6"],
  sans: "sans",
};

interface Series {
  name: string;
  data: [number, number][];
  lineStyle: { color?: string; width?: number };
  markArea?: { data: [{ xAxis: number }, { xAxis: number }][]; itemStyle: { color: string } };
  markLine?: { data: { xAxis: number }[]; lineStyle: { color: string; width: number; type: unknown } };
}

interface Opt {
  xAxis: { type: string; min: number; max: number };
  dataZoom: { type: string; startValue: number; endValue: number }[];
  series: Series[];
}

function option(): Opt {
  return fake.option as unknown as Opt;
}

/** A report whose analysed window starts at price index `k` (a visible left band when k >= 2). */
function withStartAt(k: number) {
  const r = cloneReport();
  r.data.actual_start = r.price_series.dates[k] as string;
  return r;
}

beforeEach(() => {
  fake.option = null;
  fake.handlers.clear();
  vi.clearAllMocks();
});

describe("priceModel", () => {
  it("builds the side-table rows of the static report", () => {
    const m = priceModel(mockReport);
    expect(m?.rows).toEqual([
      { label: "First", sub: "8 Aug 2024", value: "486.91", muted: false },
      { label: "End of factor data", sub: "30 Sep 2026", value: expect.any(String), muted: false },
      { label: "Latest", sub: "13 Nov 2026", value: expect.any(String), muted: false },
      { label: "After factor data", sub: "32 days, raw, not analysed", value: "+1.23%", muted: true },
    ]);
  });

  it("marks the right cut only, with the specified label, when the analysis starts on the first day", () => {
    const m = priceModel(mockReport);
    expect(m?.endLabel).toBe("Not analysed: factor data ends 30 Sep 2026");
    expect(m?.startLabel).toBeNull();
    expect(m?.startCut).toBeNull();
    expect(m?.canShowFull).toBe(false);
  });

  it("marks the left cut when at least two earlier days are not analysed, but not for one base day", () => {
    const r = withStartAt(100);
    const m = priceModel(r);
    expect(m?.startLabel).toBe(`Not analysed: before ${dateLong(r.data.actual_start)}`);
    expect(priceModel(withStartAt(1))?.startLabel).toBeNull();
  });

  it("loads the window from 10% of the analysed span before the first analysed day", () => {
    const r = withStartAt(100);
    const m = priceModel(r);
    const span = toMs(r.data.actual_end) - toMs(r.data.actual_start);
    expect(m?.initialStartMs).toBeCloseTo(toMs(r.data.actual_start) - 0.1 * span, 0);
    expect(m?.canShowFull).toBe(true);
  });

  it("returns null with fewer than two finite prices", () => {
    const r = cloneReport();
    r.price_series.adj_close = r.price_series.adj_close.map((v, i) => (i === 0 ? v : null));
    expect(priceModel(r)).toBeNull();
  });

  it("shows no 'End of factor data' row and one band over the whole window when nothing is covered", () => {
    const r = cloneReport();
    r.price_series.factor_coverage_end = "2000-01-01";
    const m = priceModel(r);
    expect(m?.cut).toBe(-1);
    expect(m?.rows.map((x) => x.label)).toEqual(["First", "Latest", "After factor data"]);
    expect(m?.endLabel).toBe("Not analysed: factor data ends 1 Jan 2000");
  });

  it("omits the right cut and the After row when the factor data reach the last price", () => {
    const r = cloneReport();
    r.price_series.factor_coverage_end = r.price_series.dates[r.price_series.dates.length - 1] as string;
    r.data.uncovered = { ...r.data.uncovered, n: 0, compounded_return: null };
    const m = priceModel(r);
    expect(m?.endLabel).toBeNull();
    expect(m?.rows.map((x) => x.label)).toEqual(["First", "End of factor data", "Latest"]);
  });
});

describe("priceOption", () => {
  it("uses a true time axis over the first to last price date", () => {
    const m = priceModel(mockReport);
    if (!m) throw new Error("no model");
    fake.option = priceOption(m, tokens, { full: false }) as never;
    const o = option();
    expect(o.xAxis.type).toBe("time");
    expect(o.xAxis.min).toBe(toMs("2024-08-08"));
    expect(o.xAxis.max).toBe(toMs("2026-11-13"));
  });

  it("asks for few y ticks (design D4: three to four labels)", () => {
    const m = priceModel(mockReport);
    if (!m) throw new Error("no model");
    fake.option = priceOption(m, tokens, { full: false }) as never;
    const y = (fake.option as unknown as { yAxis: { splitNumber: number } }).yAxis;
    expect(y.splitNumber).toBeLessThanOrEqual(2);
  });

  it("shades the right band with the grid token and a 1 px dashed rule at its true position", () => {
    const m = priceModel(mockReport);
    if (!m) throw new Error("no model");
    fake.option = priceOption(m, tokens, { full: true }) as never;
    const bands = option().series[0] as Series;
    expect(bands.markArea?.itemStyle.color).toBe("GRID");
    expect(bands.markArea?.data).toEqual([[{ xAxis: toMs("2026-09-30") }, { xAxis: toMs("2026-11-13") }]]);
    expect(bands.markLine?.data).toEqual([{ xAxis: toMs("2026-09-30") }]);
    expect(bands.markLine?.lineStyle).toEqual({ color: "INK3", width: 1, type: [3, 3] });
  });

  it("shades both non-analysed ends, each as wide as its dates", () => {
    const r = withStartAt(100);
    const m = priceModel(r);
    if (!m) throw new Error("no model");
    fake.option = priceOption(m, tokens, { full: true }) as never;
    const bands = option().series[0] as Series;
    expect(bands.markArea?.data).toEqual([
      [{ xAxis: toMs(r.price_series.dates[0] as string) }, { xAxis: toMs(r.data.actual_start) }],
      [{ xAxis: toMs("2026-09-30") }, { xAxis: toMs("2026-11-13") }],
    ]);
    expect(bands.markLine?.data).toEqual([{ xAxis: toMs(r.data.actual_start) }, { xAxis: toMs("2026-09-30") }]);
  });

  it("draws a 1.5 px ink line through the cut and a muted line after it", () => {
    const m = priceModel(mockReport);
    if (!m) throw new Error("no model");
    fake.option = priceOption(m, tokens, { full: true }) as never;
    const [, main, tail] = option().series as [Series, Series, Series];
    expect(main.lineStyle).toMatchObject({ color: "INK", width: 1.5 });
    expect(tail.lineStyle).toMatchObject({ color: "INK3", width: 1.5 });
    expect(main.data.at(-1)?.[0]).toBe(toMs("2026-09-30"));
    expect(tail.data[0]?.[0]).toBe(toMs("2026-09-30"));
    expect(tail.data.at(-1)?.[0]).toBe(toMs("2026-11-13"));
  });

  it("zooms to the loaded window or to the whole history", () => {
    const m = priceModel(withStartAt(100));
    if (!m) throw new Error("no model");
    const loaded = priceOption(m, tokens, { full: false }) as unknown as Opt;
    const full = priceOption(m, tokens, { full: true }) as unknown as Opt;
    expect(loaded.dataZoom[0]).toMatchObject({ type: "inside", startValue: m.initialStartMs, endValue: toMs("2026-11-13") });
    expect(full.dataZoom[0]?.startValue).toBe(toMs("2024-08-08"));
  });

  it("draws every price, so a one-day spike survives on a long series and nothing is downsampled (F11)", () => {
    const r = cloneReport();
    const n = 8640;
    const spikeAt = 4321;
    const day0 = Date.UTC(1990, 0, 1);
    r.price_series.dates = Array.from({ length: n }, (_, i) => new Date(day0 + i * 86_400_000).toISOString().slice(0, 10));
    r.price_series.adj_close = Array.from({ length: n }, (_, i) => (i === spikeAt ? 1000 : 100 + (i % 7)));
    r.price_series.factor_coverage_end = r.price_series.dates[n - 1] as string;
    r.data.actual_start = r.price_series.dates[0] as string;
    r.data.actual_end = r.price_series.dates[n - 1] as string;
    const m = priceModel(r);
    if (!m) throw new Error("no model");
    const opt = priceOption(m, tokens, { full: true }) as unknown as Opt;
    const line = opt.series.find((s) => s.name === "Adjusted close");
    expect(line?.data).toHaveLength(n);
    expect(line?.data[spikeAt]).toEqual([toMs(r.price_series.dates[spikeAt] as string), 1000]);
    // ECharts draws every point unless a series asks for `sampling` (lttb, average, min, max).
    for (const s of opt.series) expect(s).not.toHaveProperty("sampling");
  });

  it("escapes every string in the tooltip", () => {
    expect(escapeHtml(`<b>"x" & 'y'</b>`)).toBe("&lt;b&gt;&quot;x&quot; &amp; &#39;y&#39;&lt;/b&gt;");
    expect(tooltipHtml(toMs("2025-03-04"), 1234.5)).toBe("4 Mar 2025<br/><b>1,234.50</b>");
  });
});

describe("visibleLabels", () => {
  it("shows a label only while its band is inside the view", () => {
    const m = priceModel(withStartAt(100));
    if (!m) throw new Error("no model");
    const start = m.startLabel;
    const end = m.endLabel;
    expect(visibleLabels(m, { start: toMs("2024-08-08"), end: toMs("2026-11-13") })).toEqual({ start, end });
    expect(visibleLabels(m, { start: toMs("2025-06-01"), end: toMs("2026-01-01") })).toEqual({ start: null, end: null });
    expect(visibleLabels(m, { start: toMs("2024-08-08"), end: toMs("2024-12-01") }).end).toBeNull();
  });
});

describe("PricePanel", () => {
  it("renders the question, the side table and the footnote", () => {
    const { container } = render(<PricePanel report={mockReport} />);
    expect(screen.getByRole("heading", { level: 2, name: "Price" })).toBeTruthy();
    const outcome = container.querySelector(".q");
    expect(outcome?.textContent).toBe(
      "With dividends reinvested, SPY rose 30.5% over the analysed range (8 Aug 2024 to 30 Sep 2026). The last 32 price days are charted but not analysed.",
    );
    expect(outcome?.getAttribute("title")).toBe("How has the price moved over the window? Shaded days are not in the analysis.");
    const rows = Array.from(container.querySelectorAll("table.side tbody tr")).map((tr) => tr.textContent);
    expect(rows[0]).toBe("First8 Aug 2024486.91");
    expect(rows[3]).toBe("After factor data32 days, raw, not analysed+1.23%");
    expect(container.querySelector(".foot > p")?.textContent).toBe(
      "Adjusted close from MOCK price source (Adj Close), for context only; no statistic uses the price line.",
    );
  });

  it("hides the chart from assistive technology; the table carries the numbers", () => {
    const { container } = render(<PricePanel report={mockReport} />);
    expect(container.querySelector(".price-chart")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("shows the right label above the chart and no left label when the analysis starts on the first day", () => {
    const { container } = render(<PricePanel report={mockReport} />);
    const tags = Array.from(container.querySelectorAll(".zone-tag")).map((t) => t.textContent);
    expect(tags).toEqual(["", "Not analysed: factor data ends 30 Sep 2026"]);
    expect(screen.queryByRole("button", { name: /Show/ })).toBeNull();
  });

  it("shows both labels with both ends not analysed", () => {
    const r = withStartAt(100);
    const { container } = render(<PricePanel report={r} />);
    const tags = Array.from(container.querySelectorAll(".zone-tag")).map((t) => t.textContent);
    expect(tags[0]).toMatch(/^Not analysed: before \d+ \w{3} 2024$/);
    expect(tags[1]).toBe("Not analysed: factor data ends 30 Sep 2026");
  });

  it("toggles between the analysed range and the full history with a real button", () => {
    const r = withStartAt(100);
    const m = priceModel(r);
    if (!m) throw new Error("no model");
    render(<PricePanel report={r} />);
    expect((option() as unknown as Opt).dataZoom[0]?.startValue).toBe(m.initialStartMs);
    const button = screen.getByRole("button", { name: "Show full history" });
    expect(button.tagName).toBe("BUTTON");
    expect(button.getAttribute("type")).toBe("button");
    // A native button is in the tab order and Enter or Space fire a click.
    fireEvent.click(button);
    expect((option() as unknown as Opt).dataZoom[0]?.startValue).toBe(toMs("2024-08-08"));
    fireEvent.click(screen.getByRole("button", { name: "Show analysed range" }));
    expect((option() as unknown as Opt).dataZoom[0]?.startValue).toBe(m.initialStartMs);
  });

  it("starts on the analysed window again for a new report", () => {
    const first = withStartAt(100);
    const { rerender } = render(<PricePanel report={first} />);
    fireEvent.click(screen.getByRole("button", { name: "Show full history" }));
    rerender(<PricePanel report={withStartAt(120)} />);
    expect(screen.getByRole("button", { name: "Show full history" })).toBeTruthy();
  });

  it("moves the labels with wheel zoom", () => {
    const r = withStartAt(100);
    const { container } = render(<PricePanel report={r} />);
    expect(fake.handlers.has("datazoom")).toBe(true);
    fake.chart.getOption.mockReturnValue({ dataZoom: [{ startValue: toMs("2025-06-01"), endValue: toMs("2026-01-01") }] });
    act(() => fake.handlers.get("datazoom")?.());
    const tags = Array.from(container.querySelectorAll(".zone-tag")).map((t) => t.textContent);
    expect(tags).toEqual(["", ""]);
  });

  it("shows an empty state, no chart and no footnote when there are no prices", () => {
    const r = cloneReport();
    r.price_series.dates = [];
    r.price_series.adj_close = [];
    const { container } = render(<PricePanel report={r} />);
    expect(screen.getByText(/fewer than two price points/)).toBeTruthy();
    expect(screen.getByText("Check the ticker symbol or choose a later start date.")).toBeTruthy();
    expect(container.querySelector(".price-chart")).toBeNull();
    expect(container.querySelector(".foot")).toBeNull();
  });
});
