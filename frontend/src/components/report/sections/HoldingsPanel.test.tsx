import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import holdingsFixture from "@fixtures/sections/holdings.json";
import type { FactorReport, HoldingRow, HoldingsSection } from "../../../api/types";
import { dateLong } from "../../../format";
import { cloneReport } from "../../../test/fixture";
import { HoldingsPanel } from "./HoldingsPanel";
import { buildTree, outcomeSentence, tops } from "./holdingsModel";

const backend = holdingsFixture as unknown as HoldingsSection;

function row(
  id: string,
  kind: HoldingRow["kind"],
  label: string,
  depth: number,
  parent: string | null,
  figures: [number | null, number | null, number, number | null],
  ticker: string | null = null,
): HoldingRow {
  const [target_weight, end_weight, contribution, risk_share] = figures;
  return { id, kind, label, ticker, depth, parent_id: parent, target_weight, end_weight, contribution, risk_share };
}

/** Equities (a sub-asset class with two holdings, one with a single holding), Fixed Income (one single), cash and cost. */
function multi(): HoldingsSection {
  return {
    ...backend,
    total_return: 0.3,
    risk_share_reason: null,
    rows: [
      row("g:eq", "group", "Equities", 0, null, [0.6, 0.65, 0.24, 0.8]),
      row("g:na", "group", "Equity N. America - Large Cap", 1, "g:eq", [0.45, 0.5, 0.18, 0.6]),
      row("i:ivv", "holding", "iShares Core S&P 500", 2, "g:na", [0.3, 0.33, 0.12, 0.4], "IVV"),
      row("i:qqq", "holding", "Invesco QQQ Trust", 2, "g:na", [0.15, 0.17, 0.06, 0.2], "QQQ"),
      row("g:eu", "group", "Equity Europe - Large Cap", 1, "g:eq", [0.15, 0.15, 0.06, 0.2]),
      row("i:iev", "holding", "Europe 350", 2, "g:eu", [0.15, 0.15, 0.06, 0.2], "IEV"),
      row("g:fi", "group", "Fixed Income", 0, null, [0.3, 0.27, 0.05, 0.15]),
      row("g:gov", "group", "Government Bonds", 1, "g:fi", [0.3, 0.27, 0.05, 0.15]),
      row("i:ief", "holding", "Government Bonds", 2, "g:gov", [0.3, 0.27, 0.05, 0.15], "IEF"),
      row("cash", "cash", "USD cash", 0, null, [0.1, 0.08, 0.01, 0.05]),
      row("cost", "cost", "Trading cost", 0, null, [null, null, -0.002, null]),
    ],
  };
}

function report(section: HoldingsSection | null): FactorReport {
  const r = cloneReport();
  if (section !== null) r.holdings = section;
  return r;
}

const pp = (x: number) => `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(1)}`;
const share = (x: number) => `${(x * 100).toFixed(1)}%`;

function rowNamed(name: string | RegExp): HTMLElement {
  return screen.getByRole("row", { name: typeof name === "string" ? new RegExp(`^${name}`) : name });
}

function rowOf(el: HTMLElement) {
  const cells = within(el).getAllByRole("cell");
  return {
    target: cells[0]?.textContent,
    end: cells[1]?.textContent,
    ret: cells[2]?.textContent,
    risk: cells[3]?.textContent,
  };
}

describe("HoldingsPanel", () => {
  it("renders nothing for a report without the section (a ticker report)", () => {
    const { container } = render(<HoldingsPanel report={report(null)} />);
    expect(container.innerHTML).toBe("");
  });

  it("draws the rows in tree order, then cash, cost and the total", () => {
    const section = multi();
    render(<HoldingsPanel report={report(section)} />);
    const names = screen
      .getAllByRole("row")
      .slice(1)
      .map((r) => within(r).getAllByRole("rowheader")[0]?.querySelector(".nm")?.textContent?.trim());
    expect(names).toEqual([
      "Equities 3 holdings",
      "Equity N. America - Large Cap",
      "IVV",
      "QQQ",
      "Equity Europe - Large Cap",
      "Fixed Income 1 holding",
      "Government Bonds",
      "USD cash",
      "Trading cost",
      "Total",
    ]);
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Holding",
      "Target",
      "End",
      "Return (pp)",
      "Risk share",
    ]);
  });

  it("shows target, end, return in points and risk share of each row from the data", () => {
    const section = multi();
    render(<HoldingsPanel report={report(section)} />);
    const eq = section.rows[0] as HoldingRow;
    const figures = rowOf(rowNamed("Equities"));
    expect(figures).toEqual({
      target: share(eq.target_weight as number),
      end: share(eq.end_weight as number),
      ret: pp(eq.contribution),
      risk: share(eq.risk_share as number),
    });
    const cost = rowOf(rowNamed("Trading cost"));
    expect(cost).toEqual({ target: "–", end: "–", ret: pp(-0.002), risk: "–" });
    expect(within(rowNamed("Trading cost")).getByText(pp(-0.002)).className).toContain("num-neg");
    expect(within(rowNamed("Equities")).getByText(pp(eq.contribution)).className).toContain("num-pos");
  });

  it("draws the risk bar at the risk share of the row", () => {
    const section = multi();
    const { container } = render(<HoldingsPanel report={report(section)} />);
    const bar = container.querySelector('[data-row="g:eq"] .sbar') as HTMLElement;
    expect(bar.style.getPropertyValue("--p")).toBe(`${(section.rows[0] as HoldingRow).risk_share! * 100}%`);
    expect(bar.getAttribute("aria-hidden")).toBe("true");
  });

  it("folds an asset class with its caret and with Collapse all, and opens it again", () => {
    render(<HoldingsPanel report={report(multi())} />);
    expect(screen.queryByRole("row", { name: /^IVV/ })).not.toBeNull();
    const caret = screen.getByRole("button", { name: "Equities" });
    expect(caret.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(caret);
    expect(caret.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("row", { name: /^IVV/ })).toBeNull();
    expect(screen.queryByRole("row", { name: /^Equity Europe/ })).toBeNull();
    expect(screen.queryByRole("row", { name: /^Government Bonds/ })).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Collapse all" }));
    expect(screen.queryByRole("row", { name: /^Government Bonds/ })).toBeNull();
    // Cash, cost and total stay.
    expect(screen.queryByRole("row", { name: /^USD cash/ })).not.toBeNull();
    expect(screen.queryByRole("row", { name: /^Total/ })).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Expand all" }));
    expect(screen.queryByRole("row", { name: /^IVV/ })).not.toBeNull();
    expect(screen.queryByRole("row", { name: /^Government Bonds/ })).not.toBeNull();
  });

  it("gives the caret to asset classes only, and keeps it keyboard-operable (a button)", () => {
    render(<HoldingsPanel report={report(multi())} />);
    const carets = screen.getAllByRole("button").filter((b) => b.classList.contains("caret"));
    expect(carets.map((b) => b.getAttribute("aria-label"))).toEqual(["Equities", "Fixed Income"]);
    for (const c of carets) expect(c.tagName).toBe("BUTTON");
  });

  it("shows a sub-asset class with one holding as one row with the ticker on its sub-line", () => {
    const section = multi();
    render(<HoldingsPanel report={report(section)} />);
    const europe = rowNamed("Equity Europe");
    expect(within(europe).getByText("IEV").tagName).toBe("B");
    expect(within(europe).getByText(/Europe 350/)).toBeTruthy();
    // No row of its own for the holding, and the figures are the row's.
    expect(screen.queryByRole("row", { name: /^IEV/ })).toBeNull();
    const eu = section.rows.find((r) => r.id === "g:eu") as HoldingRow;
    expect(rowOf(europe).ret).toBe(pp(eu.contribution));
    // When the holding has the name of its group, the sub-line is the ticker alone.
    const gov = rowNamed("Government Bonds");
    expect(gov.querySelector(".sb")?.textContent).toBe("IEF");
    // A sub-asset class with several holdings counts them and lists them below.
    expect(rowNamed("Equity N. America").querySelector(".sb")?.textContent).toBe("2 holdings");
    expect(rowNamed("IVV").querySelector(".sb")?.textContent).toBe("iShares Core S&P 500");
  });

  it("totals the target and end weights, the return and the risk shares of the top rows", () => {
    const section = multi();
    render(<HoldingsPanel report={report(section)} />);
    const top = section.rows.filter((r) => r.parent_id === null);
    const sum = (pick: (r: HoldingRow) => number | null) => top.reduce((a, r) => a + (pick(r) ?? 0), 0);
    expect(rowOf(rowNamed("Total"))).toEqual({
      target: share(sum((r) => r.target_weight)),
      end: share(sum((r) => r.end_weight)),
      ret: pp(section.total_return),
      risk: share(sum((r) => r.risk_share)),
    });
    expect(screen.getByText(/Total return after cost:/).textContent).toBe(
      `Total return after cost: ${pp(section.total_return)}% over ${dateLong(section.window_start)} to ${dateLong(section.window_end)}`,
    );
  });

  it("states the outcome from the data: top asset class, its points, the total points and its risk share", () => {
    const section = multi();
    const { container } = render(<HoldingsPanel report={report(section)} />);
    const eq = section.rows[0] as HoldingRow;
    const expected = `${eq.label} gave ${Math.round(eq.contribution * 100)} of the ${Math.round(section.total_return * 100)} points of return and ${Math.round((eq.risk_share as number) * 100)}% of the risk.`;
    expect(container.querySelector("p.q.outcome")?.textContent).toBe(expected);
    expect(expected).toBe("Equities gave 24 of the 30 points of return and 80% of the risk.");
  });

  it("names the asset class with the most return, not the first one", () => {
    const section = multi();
    section.rows[0] = { ...(section.rows[0] as HoldingRow), contribution: 0.02 };
    const text = outcomeSentence(section, tops(buildTree(section.rows)).classes);
    expect(text?.startsWith("Fixed Income gave 5 of the 30 points")).toBe(true);
  });

  it("shows a dash for the risk share and the reason as a footnote when no risk share is defined", () => {
    const section = multi();
    section.risk_share_reason = "Risk shares need at least 60 days of returns.";
    for (const r of section.rows) r.risk_share = null;
    const { container } = render(<HoldingsPanel report={report(section)} />);
    for (const r of screen.getAllByRole("row").slice(1)) expect(rowOf(r).risk).toBe("–");
    expect(container.querySelectorAll(".sbar")).toHaveLength(0);
    expect(container.querySelector("p.foot-note")?.textContent).toBe(section.risk_share_reason);
    expect(container.querySelector("p.q.outcome")?.textContent).toBe(
      "Equities gave 24 of the 30 points of return.",
    );
  });

  it("draws the backend fixture: one row per single-holding group, cash, cost and the total", () => {
    const { container } = render(<HoldingsPanel report={report(backend)} />);
    expect(container.querySelector("section#holdings h2")?.textContent).toBe("Holdings");
    const top = backend.rows.filter((r) => r.parent_id === null);
    const rows = screen.getAllByRole("row").slice(1);
    // Two asset classes, each with one sub-asset class holding one holding, then cash, cost, total.
    expect(rows).toHaveLength(2 * 2 + 3);
    expect(within(rowNamed("US Large Cap")).getByText("SPY")).toBeTruthy();
    expect(rowOf(rowNamed("Total")).ret).toBe(pp(backend.total_return));
    expect(top.reduce((a, r) => a + r.contribution, 0)).toBeCloseTo(backend.total_return, 9);
  });

  it("has the help text and the method note, with no formula", () => {
    const { container } = render(<HoldingsPanel report={report(multi())} />);
    const foot = container.querySelector(".foot") as HTMLElement;
    expect(foot.textContent).toContain("Return is in percentage points (pp)");
    expect(within(foot).getByText("How this is computed")).toBeTruthy();
    expect(foot.textContent).not.toMatch(/[=Σ∑]|Cov\(|Var\(/);
  });

  it("is a plain table; the caret carries the expanded state and names the rows it folds", () => {
    const { container } = render(<HoldingsPanel report={report(multi())} />);
    expect(screen.getByRole("table", { name: "Holdings by asset class" })).toBeTruthy();
    expect(container.querySelector("[aria-level], [aria-expanded]:not(button)")).toBeNull();
    const caret = screen.getByRole("button", { name: "Equities" });
    expect(caret.getAttribute("aria-expanded")).toBe("true");
    const ids = (caret.getAttribute("aria-controls") ?? "").split(" ");
    // The rows below Equities, in order: its two sub-asset classes and the two holdings of the first.
    expect(ids.map((id) => container.querySelector(`[id="${id}"]`)?.getAttribute("data-row"))).toEqual([
      "g:na",
      "i:ivv",
      "i:qqq",
      "g:eu",
    ]);
  });

  it("uses the 'did best with' wording when the leader gave more than the total", () => {
    const section = multi();
    section.total_return = 0.1;
    const text = outcomeSentence(section, tops(buildTree(section.rows)).classes);
    expect(text).toBe("The portfolio returned +10.0 points. Equities did best with +24.0 points and 80% of the risk.");
  });

  it("explains that a cash line counts in the Cash row", () => {
    const { container } = render(<HoldingsPanel report={report(multi())} />);
    expect(container.querySelector(".foot")?.textContent).toContain("a cash line counts in the Cash row");
  });
});
