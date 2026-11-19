import { describe, expect, it } from "vitest";
import {
  addLineWithWeight,
  checks,
  classTotals,
  earliestCommonStart,
  formatPercent,
  isShortHistory,
  libraryById,
  lineCount,
  nudge,
  nudgeWeight,
  parsePercent,
  removeNode,
  renameTree,
  runnable,
  withCost,
} from "./composer";
import { LIBRARY, lib } from "./testLibrary";
import {
  addInstrument,
  addLine,
  emptyTree,
  instruments,
  normalise,
  remainder,
  remainderToCash,
  setWeight,
  swapInstrument,
  totalWeight,
} from "./tree";

const BY_ID = libraryById(LIBRARY);

function sample() {
  let t = emptyTree("Sample", 10);
  t = addLineWithWeight(t, lib("eq_na_large"), 0.5);
  t = addLineWithWeight(t, lib("fi_na_gov"), 0.3);
  return t;
}

describe("weight text", () => {
  it("parses typed percent text to a fraction", () => {
    expect(parsePercent("12")).toBeCloseTo(0.12, 12);
    expect(parsePercent("12.5")).toBeCloseTo(0.125, 12);
    expect(parsePercent("12,5 %")).toBeCloseTo(0.125, 12);
    expect(parsePercent("0")).toBe(0);
    expect(parsePercent("100")).toBe(1);
  });

  it("refuses text that is not a number from 0 to 100", () => {
    for (const bad of [
      "",
      " ",
      "abc",
      "-1",
      "100.5",
      "1e2",
      "12..5",
      ".",
      "5%%",
    ])
      expect(parsePercent(bad)).toBeNull();
  });

  it("formats with one decimal, or two when needed", () => {
    expect(formatPercent(0.24)).toBe("24.0");
    expect(formatPercent(0)).toBe("0.0");
    expect(formatPercent(1 / 3)).toBe("33.33");
    expect(formatPercent(0.125)).toBe("12.5");
    expect(formatPercent(0.1234)).toBe("12.34");
  });

  it("nudges by 0.5 points, between 0 and 100, without float drift", () => {
    expect(nudgeWeight(0.1, 1)).toBeCloseTo(0.105, 12);
    expect(nudgeWeight(0.105, -1)).toBeCloseTo(0.1, 12);
    expect(nudgeWeight(0.002, -1)).toBe(0);
    expect(nudgeWeight(0.998, 1)).toBe(1);
    let w = 0.1;
    for (let i = 0; i < 30; i++) w = nudgeWeight(w, 1);
    expect(w).toBeCloseTo(0.25, 12);
  });

  it("nudges one instrument of a tree and ignores an unknown id", () => {
    const t = sample();
    const id = instruments(t)[0]?.id ?? "";
    expect(instruments(nudge(t, id, 1))[0]?.weight).toBeCloseTo(0.505, 12);
    expect(nudge(t, "nope", 1)).toBe(t);
  });
});

describe("library helpers", () => {
  it("flags a proxy that starts after 2010 as a short history", () => {
    expect(isShortHistory(lib("alt_crypto"))).toBe(true);
    expect(isShortHistory(lib("fi_na_hy"))).toBe(false);
    expect(isShortHistory({ first_date: "2010-12-31" })).toBe(false);
    expect(isShortHistory({ first_date: "2011-01-03" })).toBe(true);
    expect(isShortHistory({ first_date: null })).toBe(false);
  });
});

describe("edits on top of tree.ts", () => {
  it("adds a line with a weight, and a second add of the same line changes nothing", () => {
    const t = sample();
    expect(lineCount(t)).toBe(2);
    expect(totalWeight(t)).toBeCloseTo(0.8, 12);
    expect(addLineWithWeight(t, lib("eq_na_large"), 0.9)).toEqual(t);
  });

  it("swaps a ticker and keeps the weight", () => {
    const t = sample();
    const id = instruments(t)[0]?.id ?? "";
    const swapped = swapInstrument(t, id, "SPY");
    expect(instruments(swapped)[0]).toMatchObject({
      ticker: "SPY",
      weight: 0.5,
    });
  });

  it("normalises, and puts the remainder in USD cash", () => {
    const t = sample();
    expect(totalWeight(normalise(t))).toBeCloseTo(1, 12);
    const cash = remainderToCash(t, LIBRARY);
    expect(totalWeight(cash)).toBeCloseTo(1, 12);
    expect(remainder(cash)).toBe(0);
    expect(
      instruments(cash).some(
        (i) => i.kind === "cash" && Math.abs(i.weight - 0.2) < 1e-12,
      ),
    ).toBe(true);
  });

  it("removes the line with its last instrument, and only the instrument when more are left", () => {
    let t = sample();
    const sub = t.root.children[0]?.children[0];
    const only = sub?.children[0]?.id ?? "";
    expect(lineCount(removeNode(t, only))).toBe(1);
    t = addInstrument(t, sub?.id ?? "", "QQQ");
    const after = removeNode(t, only);
    expect(lineCount(after)).toBe(2);
    expect(instruments(after).map((i) => i.ticker)).toContain("QQQ");
    expect(instruments(after).map((i) => i.id)).not.toContain(only);
  });

  it("renames the portfolio and bounds the cost", () => {
    const t = renameTree(sample(), "Other");
    expect(t.name).toBe("Other");
    expect(t.root.label).toBe("Other");
    expect(withCost(t, 25).cost_bps).toBe(25);
    expect(withCost(t, -5).cost_bps).toBe(0);
    expect(withCost(t, 5000).cost_bps).toBe(1000);
    expect(withCost(t, Number.NaN)).toBe(t);
  });
});

describe("the live panel", () => {
  it("ranks asset classes by weight", () => {
    const rows = classTotals(sample());
    expect(rows.map((r) => r.label)).toEqual(["Equities", "Fixed Income"]);
    expect(rows[0]?.weight).toBeCloseTo(0.5, 12);
  });

  it("names the leaf that sets the earliest common start, and ignores 0% leaves", () => {
    let t = sample();
    expect(earliestCommonStart(t, BY_ID)).toEqual({
      date: "2002-07-30",
      by: "IEF",
    });
    t = addLineWithWeight(t, lib("fi_eur_gov"), 0);
    expect(earliestCommonStart(t, BY_ID).by).toBe("IEF");
    const igov = instruments(t).find((i) => i.ticker === "IGOV");
    t = setWeight(t, igov?.id ?? "", 0.1);
    expect(earliestCommonStart(t, BY_ID)).toEqual({
      date: "2009-01-30",
      by: "IGOV",
    });
    expect(earliestCommonStart(emptyTree("E"), BY_ID)).toEqual({
      date: null,
      by: null,
    });
  });

  it("does not use the start of a swapped ticker", () => {
    let t = sample();
    const first = instruments(t)[0]?.id ?? "";
    t = swapInstrument(t, first, "SPY");
    expect(earliestCommonStart(t, BY_ID).by).toBe("IEF");
  });

  it("checks: unallocated to USD cash, late starts, listed proxies, USD-listed", () => {
    let t = sample();
    t = addLineWithWeight(t, lib("alt_crypto"), 0.05);
    t = addLineWithWeight(t, lib("alt_pe"), 0.05);
    const list = checks(t, BY_ID);
    const ids = list.map((c) => c.id);
    expect(ids).toContain("unallocated");
    expect(list.find((c) => c.id === "unallocated")?.title).toContain("10.0%");
    const crypto = lib("alt_crypto");
    expect(list.find((c) => c.id.startsWith("late-"))?.title).toBe(
      `${crypto.proxy} starts ${String(crypto.first_date).slice(0, 4)}.`,
    );
    expect(list.find((c) => c.id === "listed")?.title).toBe(
      `${String(crypto.proxy)}, PSP: listed proxies.`,
    );
    expect(list.find((c) => c.id === "usd")?.title).toBe(
      "All 4 instruments are USD-listed.",
    );
  });

  it("shows the over-100% error once, and says swapped tickers are checked on the run", () => {
    let t = sample();
    t = setWeight(t, instruments(t)[0]?.id ?? "", 0.9);
    t = swapInstrument(t, instruments(t)[1]?.id ?? "", "XYZ");
    const list = checks(t, BY_ID);
    expect(list.filter((c) => c.tone === "error")).toHaveLength(1);
    expect(list.find((c) => c.id === "over")?.title).toBe(
      "Weights add up to 120.0%.",
    );
    expect(list.find((c) => c.id === "usd-run")?.title).toContain("XYZ");
  });

  it("says so when the tree is empty or has no weight", () => {
    expect(checks(emptyTree("E"), BY_ID)[0]?.id).toBe("empty");
    expect(
      checks(addLine(emptyTree("E"), lib("eq_na_large")), BY_ID)[0]?.id,
    ).toBe("no-weight");
  });

  it("decides whether the tree can run", () => {
    expect(runnable(emptyTree("E"))).toEqual({
      ok: false,
      reason: "Add a sub-asset class first.",
    });
    expect(runnable(addLine(emptyTree("E"), lib("eq_na_large"))).ok).toBe(
      false,
    );
    expect(runnable(sample())).toEqual({ ok: true, reason: null });
    const over = setWeight(sample(), instruments(sample())[0]?.id ?? "", 0.9);
    expect(runnable(over).ok).toBe(false);
    expect(runnable(over).reason).toMatch(/more than 100%/);
  });
});
