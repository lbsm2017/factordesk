import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cloneReport, mockReport } from "../../test/fixture";
import { ReturnPanel } from "./ReturnPanel";
import { RiskPanel } from "./RiskPanel";
import { buildRollingBlock, buildRowOption, ROLLING_GROUP, RollingPanel } from "./RollingPanel";
import { readChartTokens } from "../charts/chartTokens";

const fake = vi.hoisted(() => {
  const handlers = new Map<string, () => void>();
  const makeInstance = () => ({
    group: "",
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: vi.fn(() => false),
    on: vi.fn((event: string, fn: () => void) => handlers.set(event, fn)),
    off: vi.fn(),
    getOption: vi.fn(() => ({ dataZoom: [{ startValue: 1, endValue: 2 }] })),
    dispatchAction: vi.fn(),
  });
  const instances: ReturnType<typeof makeInstance>[] = [];
  return {
    instances,
    handlers,
    init: vi.fn(() => {
      const instance = makeInstance();
      instances.push(instance);
      return instance;
    }),
    connect: vi.fn(),
    disconnect: vi.fn(),
  };
});

vi.mock("../charts/echartsCore", () => ({ init: fake.init, connect: fake.connect, disconnect: fake.disconnect }));

beforeEach(() => {
  fake.instances.length = 0;
  fake.handlers.clear();
  vi.clearAllMocks();
});

function cells(row: Element): string[] {
  return Array.from(row.querySelectorAll("th, td")).map((c) => c.textContent?.trim() ?? "");
}

describe("ReturnPanel", () => {
  it("shows every contribution, the hatched residual, the total and the memo list", () => {
    const { container } = render(<ReturnPanel report={mockReport} />);
    expect(screen.getByRole("heading", { level: 2, name: "Where the return came from" })).toBeTruthy();
    const rows = Array.from(container.querySelectorAll("tbody tr"));
    expect(rows.map((r) => cells(r).filter((_, i) => i !== 1))).toEqual([
      ["Mkt-RFMarket", "+11.57%", "Yes"],
      ["SMBSize", "+0.18%", "Yes"],
      ["HMLValue", "+0.01%", "No"],
      ["RMWProfitability", "+0.08%", "Yes"],
      ["CMAInvestment", "0.00%", "No"],
      ["AlphaUnexplained average", "+0.81%", "No"],
      ["ResidualZero by construction", "0.00%", "–"],
      ["TotalMean excess return", "+12.64%", ""],
    ]);
    expect(container.querySelector("#ret-alpha")).not.toBeNull();
    expect(container.querySelector("#ret-Mkt-RF")?.getAttribute("tabindex")).toBe("-1");
    expect(container.querySelector("tr.resid rect.hatch")).not.toBeNull();
    expect(container.querySelector("tr.alpha rect.faded")).not.toBeNull();
    expect(container.querySelector("tr.total line.total-cap")).not.toBeNull();
    expect(screen.getByText("Not in the sum")).toBeTruthy();
    expect(container.querySelectorAll(".memo li")).toHaveLength(2);
    expect(container.querySelector(".reading")?.textContent).toBe(
      "Of the 12.64% average excess return a year, market exposure accounts for 11.57%. Alpha adds +0.81%, but it is not significant.",
    );
  });

  it("keeps the footnote to one sentence plus a folded method note", () => {
    const { container } = render(<ReturnPanel report={mockReport} />);
    expect(container.querySelector(".foot > p")?.textContent).toMatch(/The rows add up exactly to the total\.$/);
    expect(container.querySelector("details.how")?.textContent).toContain("Arithmetic, not compounded");
    expect(container.querySelector("details.how")?.textContent).toContain("Identity check 0.0e+00.");
  });

  it("draws bar tables as SVG in a fixed-column table with explicit roles", () => {
    const { container } = render(<ReturnPanel report={mockReport} />);
    const table = container.querySelector("table");
    expect(table?.getAttribute("role")).toBe("table");
    expect(table?.className).toContain("bars");
    expect(container.querySelector("tbody th")?.getAttribute("role")).toBe("rowheader");
    expect(container.querySelectorAll("td.plot-cell > svg.bar-svg").length).toBe(8);
    expect(container.querySelector("tr.axis-row")?.getAttribute("aria-hidden")).toBe("true");
    expect(within(container.querySelector("tr.axis-row") as HTMLElement).getByText("0%")).toBeTruthy();
  });

  it("shows the reason and one next step when the statistic is not ok", () => {
    const report = cloneReport();
    Object.assign(report.return_contribution, {
      status: "insufficient_data",
      reason: "Too few days for an attribution.",
      factors: {},
      alpha: null,
      residual: null,
      total_annualised_mean_excess_return: null,
    });
    const { container } = render(<ReturnPanel report={report} />);
    expect(screen.getByText("Too few days for an attribution.")).toBeTruthy();
    expect(screen.getByText("Widen the date range and run the report again.")).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
    expect(container.querySelector(".foot")).toBeNull();
  });
});

describe("RiskPanel", () => {
  it("lists rows in the report's order with share, beta, factor vol and correlation", () => {
    const { container } = render(<RiskPanel report={mockReport} />);
    const rows = Array.from(container.querySelectorAll("tbody tr"));
    expect(rows.map((r) => (r.querySelector("th .fname")?.textContent ?? ""))).toEqual([
      "Mkt-RF",
      "SMB",
      "RMW",
      "CMA",
      "HML",
      "Idiosyncratic",
    ]);
    const mkt = cells(rows[0] as Element).filter((_, i) => i !== 1);
    expect(mkt[1]).toBe("99.41%");
    expect(mkt.slice(2)).toEqual(["+0.998", "10.0%", "+0.50"]);
    const hml = cells(rows[4] as Element);
    expect(hml[2]).toBe("−0.02%");
    const idio = cells(rows[5] as Element).filter((_, i) => i !== 1);
    expect(idio.slice(1)).toEqual(["0.47%", "–", "–", "–"]);
    expect(rows[5]?.querySelector("rect.hatch")).not.toBeNull();
    expect(rows[0]?.querySelector("rect.cat.c1")).not.toBeNull();
    expect(container.querySelector("th .sub.mob")?.textContent).toBe("Beta +0.998, vol 10.0%, corr +0.50");
    expect(container.querySelector("svg.bar-svg title")?.textContent).toContain("exposure +0.998 x volatility 10.0%");
  });

  it("reads the top share, the stock-specific share, total volatility and the sentences", () => {
    const { container } = render(<RiskPanel report={mockReport} />);
    expect(container.querySelector(".reading")?.textContent).toBe(
      "Mkt-RF drives 99.4% of the variance; stock-specific risk is 0.5%. Total volatility is 17.0% a year. MOCK: SMB ranks #2 by risk but only #4 by beta size.",
    );
    expect(container.querySelector("details.how")?.textContent).toContain("Euler decomposition");
  });

  it("extends the domain to the left for a negative share", () => {
    const { container } = render(<RiskPanel report={mockReport} />);
    const labels = Array.from(container.querySelectorAll("tr.axis-row .axis span")).map((s) => s.textContent);
    expect(labels).toEqual(["−50%", "0%", "50%", "100%", "150%"]);
  });

  it("shows an empty state when the statistic is not ok", () => {
    const report = cloneReport();
    Object.assign(report.risk_contribution, {
      status: "failed",
      reason: "The covariance matrix is singular.",
      factors: {},
      idiosyncratic: null,
    });
    const { container } = render(<RiskPanel report={report} />);
    expect(screen.getByText("The covariance matrix is singular.")).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
  });
});

describe("RollingPanel", () => {
  it("renders five rows with Latest, Average and Middle 80% and a title with the spread", async () => {
    const { container } = render(<RollingPanel report={mockReport} win={252} onWinChange={vi.fn()} />);
    const rows = Array.from(container.querySelectorAll("tbody tr"));
    expect(rows).toHaveLength(5);
    const rangeOf = (row?: Element) => row?.querySelector("td.range")?.firstChild?.textContent;
    expect(cells(rows[0] as Element).filter((_, i) => i !== 1).slice(0, 3)).toEqual(["Mkt-RFMarket", "+0.997", "+0.998"]);
    expect(rangeOf(rows[0])).toBe("+0.99 to +1.01");
    expect(cells(rows[1] as Element).slice(2, 4)).toEqual(["−0.160", "−0.146"]);
    expect(rangeOf(rows[1])).toBe("−0.21 to −0.07");
    const title = rows[1]?.querySelector("td.range")?.getAttribute("title") ?? "";
    expect(title).toMatch(/^Spread \d\.\d{3}, lowest [+−]\d\.\d{3}, highest [+−]\d\.\d{3}, above zero in \d+% of windows$/);
    expect(rows[0]?.querySelector("td.range")?.getAttribute("title")).toContain("above zero in 100% of windows");
    expect(container.querySelector("tr.axis-row .xl")).not.toBeNull();
    expect(container.querySelectorAll(".plot.mini")).toHaveLength(5);
    await waitFor(() => expect(fake.init).toHaveBeenCalledTimes(5));
  });

  it("joins the five charts in one group so zoom and hover move together", async () => {
    render(<RollingPanel report={mockReport} win={252} onWinChange={vi.fn()} />);
    await waitFor(() => expect(fake.instances).toHaveLength(5));
    await waitFor(() => expect(fake.instances.every((i) => i.group === ROLLING_GROUP)).toBe(true));
    expect(fake.connect).toHaveBeenCalledWith(ROLLING_GROUP);
    await waitFor(() => expect(fake.instances.every((i) => i.setOption.mock.calls.length > 0)).toBe(true));
    const option = fake.instances[0]?.setOption.mock.calls[0]?.[0] as {
      series: { name: string; stack?: string; data: unknown[] }[];
      dataZoom: { type: string }[];
      tooltip: { trigger: string };
    };
    expect(option.series.map((s) => s.name)).toEqual(["lower", "band", "beta"]);
    expect(option.dataZoom[0]?.type).toBe("inside");
    expect(option.tooltip.trigger).toBe("axis");
  });

  it("shows the 126-day window with derived averages and puts the choice through onWinChange", () => {
    const onWinChange = vi.fn();
    const { container } = render(<RollingPanel report={mockReport} win={126} onWinChange={onWinChange} />);
    expect(container.querySelector(".win.w-126")).not.toBeNull();
    expect((screen.getByLabelText("126 days") as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText("252 days") as HTMLInputElement).checked).toBe(false);
    expect(container.querySelector(".foot")?.textContent).toContain("previous 126 trading days");
    fireEvent.click(screen.getByLabelText("252 days"));
    expect(onWinChange).toHaveBeenCalledWith(252);
  });

  it("builds the row option with the common span, a pointwise band and no data for warm-up stamps", () => {
    const w = mockReport.rolling.find((x) => x.window === 252)!;
    const block = buildRollingBlock(mockReport, w)!;
    expect(block.rows).toHaveLength(5);
    const spans = block.rows.map((r) => r.hi - r.lo);
    for (const s of spans) expect(s).toBeCloseTo(spans[0] as number, 9);
    const row = block.rows[1]!;
    expect(row.ms).toHaveLength(308);
    expect(row.upper[0]! - row.lower[0]!).toBeCloseTo(2 * block.z * (row.upper[0]! - row.beta[0]!) / block.z, 9);
    const option = buildRowOption(block, row, readChartTokens()) as {
      series: { data: [number, number][] }[];
      yAxis: { min: number; max: number };
    };
    expect(option.yAxis.min).toBe(row.lo);
    expect(option.series[2]?.data).toHaveLength(308);
    expect(option.series[0]?.data[0]?.[1]).toBeCloseTo(row.lower[0] as number, 12);
  });

  it("shows a per-window reason inside the panel when one window is not ok", () => {
    const report = cloneReport();
    const w = report.rolling.find((x) => x.window === 126)!;
    Object.assign(w, { status: "insufficient_data", reason: "126 days need 126 trading days.", dates: [], window_start: [], betas: {}, se: {}, ci_z: null });
    const { container } = render(<RollingPanel report={report} win={126} onWinChange={vi.fn()} />);
    expect(screen.getByText("126 days need 126 trading days.")).toBeTruthy();
    expect(screen.getByText("Choose an earlier start date or the shorter window.")).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
    expect(screen.getByLabelText("252 days")).toBeTruthy();
  });

  it("shows one empty state and no radios when no window is ok", () => {
    const report = cloneReport();
    for (const w of report.rolling) {
      Object.assign(w, { status: "insufficient_data", reason: "Too few days.", dates: [], window_start: [], betas: {}, se: {}, ci_z: null });
    }
    const { container } = render(<RollingPanel report={report} win={252} onWinChange={vi.fn()} />);
    expect(screen.getByText("Too few days.")).toBeTruthy();
    expect(container.querySelector(".seg")).toBeNull();
    expect(container.querySelector(".foot")).toBeNull();
  });
});
