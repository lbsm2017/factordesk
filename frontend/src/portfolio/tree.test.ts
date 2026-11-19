import { describe, expect, it } from "vitest";
import {
  MAX_INSTRUMENTS,
  USD_CASH_LIBRARY_ID,
  addInstrument,
  addLine,
  emptyTree,
  instruments,
  normalise,
  remainder,
  remainderToCash,
  remove,
  rename,
  rollUp,
  setWeight,
  swapInstrument,
  totalWeight,
  validate,
  type LibraryLineLike,
  type PortfolioTree,
} from "./tree";

const LIB: LibraryLineLike[] = [
  { id: "cash_usd", asset_class: "Cash", sub_asset_class: "USD Cash", proxy: "RF", proxy_kind: "risk_free" },
  { id: "eq_global", asset_class: "Equities", sub_asset_class: "Equity Global", proxy: "ACWI", proxy_kind: "etf" },
  { id: "eq_na_large", asset_class: "Equities", sub_asset_class: "Equity N. America - Large Cap", proxy: "IVV", proxy_kind: "etf" },
  { id: "fi_tips", asset_class: "Fixed Income", sub_asset_class: "Inflation Linked Bonds (TIPS)", proxy: "TIP", proxy_kind: "etf" },
  { id: "alt_vc", asset_class: "Alternatives", sub_asset_class: "Venture Capital", proxy: null, proxy_kind: "none" },
];

function line(id: string): LibraryLineLike {
  const found = LIB.find((l) => l.id === id);
  if (found === undefined) throw new Error(id);
  return found;
}

function build(): PortfolioTree {
  let t = emptyTree("Test", 5);
  for (const id of ["eq_global", "eq_na_large", "fi_tips"]) t = addLine(t, line(id));
  return t;
}

function idOf(t: PortfolioTree, libraryId: string): string {
  const sub = t.root.children.flatMap((ac) => ac.children).find((s) => s.library_id === libraryId);
  if (sub === undefined) throw new Error(libraryId);
  return sub.children[0]!.id;
}

describe("addLine", () => {
  it("creates the asset class group and a sub group with the proxy at weight 0", () => {
    const t = addLine(emptyTree("T"), line("eq_global"));
    expect(t.root.children).toHaveLength(1);
    const ac = t.root.children[0]!;
    expect(ac.label).toBe("Equities");
    expect(ac.children[0]).toMatchObject({ kind: "group", label: "Equity Global", library_id: "eq_global" });
    expect(ac.children[0]!.children).toEqual([
      expect.objectContaining({ kind: "holding", ticker: "ACWI", weight: 0 }),
    ]);
  });

  it("reuses the asset class group and keeps the order of addition", () => {
    const t = build();
    expect(t.root.children.map((ac) => ac.label)).toEqual(["Equities", "Fixed Income"]);
    expect(t.root.children[0]!.children.map((s) => s.library_id)).toEqual(["eq_global", "eq_na_large"]);
  });

  it("does not add a line twice", () => {
    const t = build();
    expect(addLine(t, line("eq_global"))).toBe(t);
  });

  it("gives the risk-free line a cash instrument and a no-proxy line a null ticker", () => {
    const t = addLine(addLine(emptyTree("T"), line("cash_usd")), line("alt_vc"));
    const [cash, vc] = instruments(t);
    expect(cash).toMatchObject({ kind: "cash", ticker: null });
    expect(vc).toMatchObject({ kind: "holding", ticker: null, weight: 0 });
    expect(validate(t).errors).toEqual([]);
  });

  it("does not change its argument", () => {
    const t = emptyTree("T");
    const before = JSON.stringify(t);
    addLine(t, line("eq_global"));
    expect(JSON.stringify(t)).toBe(before);
  });
});

describe("addInstrument and swapInstrument", () => {
  it("adds a holding at weight 0 with a fresh id", () => {
    let t = build();
    const subId = t.root.children[0]!.children[0]!.id;
    t = addInstrument(t, subId, "VT");
    t = addInstrument(t, subId, "VTI", "Total market");
    const kids = t.root.children[0]!.children[0]!.children;
    expect(kids.map((i) => i.ticker)).toEqual(["ACWI", "VT", "VTI"]);
    expect(kids[2]).toMatchObject({ label: "Total market", weight: 0, kind: "holding" });
    expect(new Set(instruments(t).map((i) => i.id)).size).toBe(instruments(t).length);
  });

  it("leaves the tree alone for an unknown group", () => {
    const t = build();
    expect(addInstrument(t, "nope", "VT")).toBe(t);
  });

  it("swaps the ticker and keeps the weight", () => {
    let t = build();
    const id = idOf(t, "eq_global");
    t = setWeight(t, id, 0.4);
    t = swapInstrument(t, id, "VT", "Vanguard Total World");
    expect(instruments(t)[0]).toMatchObject({ ticker: "VT", label: "Vanguard Total World", weight: 0.4, kind: "holding" });
  });

  it("turns a cash instrument into a holding when swapped", () => {
    let t = addLine(emptyTree("T"), line("cash_usd"));
    t = swapInstrument(t, idOf(t, "cash_usd"), "BIL");
    expect(instruments(t)[0]).toMatchObject({ kind: "holding", ticker: "BIL" });
  });

  it("a swap to no ticker sets the weight to 0", () => {
    let t = build();
    const id = idOf(t, "eq_global");
    t = setWeight(t, id, 0.3);
    t = swapInstrument(t, id, null);
    expect(instruments(t)[0]).toMatchObject({ ticker: null, weight: 0 });
    expect(validate(t).errors).toEqual([]);
  });
});

describe("rename", () => {
  it("renames an instrument, a group, an asset class and the root", () => {
    let t = build();
    const ac = t.root.children[0]!;
    const sub = ac.children[0]!;
    t = rename(t, sub.children[0]!.id, "World");
    t = rename(t, sub.id, "World equity");
    t = rename(t, ac.id, "Stocks");
    t = rename(t, "root", "Mine");
    expect(t.root.label).toBe("Mine");
    expect(t.root.children[0]!.label).toBe("Stocks");
    expect(t.root.children[0]!.children[0]!.label).toBe("World equity");
    expect(t.root.children[0]!.children[0]!.children[0]!.label).toBe("World");
    expect(t.root.children[1]!.label).toBe("Fixed Income");
  });
});

describe("remove", () => {
  it("removes an instrument and keeps its empty line", () => {
    let t = build();
    t = remove(t, idOf(t, "eq_global"));
    expect(t.root.children[0]!.children[0]!.children).toEqual([]);
    expect(instruments(t)).toHaveLength(2);
  });

  it("removes a line with its instruments", () => {
    let t = build();
    t = remove(t, "sub_eq_global");
    expect(t.root.children[0]!.children.map((s) => s.library_id)).toEqual(["eq_na_large"]);
  });

  it("removes an asset class group that the call leaves empty", () => {
    let t = build();
    t = remove(t, "sub_fi_tips");
    expect(t.root.children.map((ac) => ac.label)).toEqual(["Equities"]);
  });

  it("removes a whole asset class group", () => {
    const t = remove(build(), "ac_equities");
    expect(t.root.children.map((ac) => ac.label)).toEqual(["Fixed Income"]);
  });

  it("cannot remove the root", () => {
    const t = build();
    expect(remove(t, "root").root.children).toHaveLength(2);
  });

  it("an unknown id changes nothing", () => {
    const t = build();
    expect(remove(t, "nope")).toEqual(t);
  });
});

describe("setWeight and rollUp", () => {
  it("sets a weight and ignores a non-finite one", () => {
    let t = build();
    const id = idOf(t, "eq_global");
    t = setWeight(t, id, 0.25);
    expect(instruments(t)[0]!.weight).toBe(0.25);
    expect(setWeight(t, id, Number.NaN)).toBe(t);
    expect(setWeight(t, id, Number.POSITIVE_INFINITY)).toBe(t);
  });

  it("every group total equals the sum of its leaves", () => {
    let t = build();
    const subId = "sub_eq_global";
    t = addInstrument(t, subId, "VT");
    const [a, b, c, d] = instruments(t);
    t = setWeight(t, a!.id, 0.1);
    t = setWeight(t, b!.id, 0.2);
    t = setWeight(t, c!.id, 0.3);
    t = setWeight(t, d!.id, 0.15);
    const totals = rollUp(t);
    expect(totals[subId]).toBeCloseTo(0.3, 12);
    expect(totals["sub_eq_na_large"]).toBeCloseTo(0.3, 12);
    expect(totals["ac_equities"]).toBeCloseTo(0.6, 12);
    expect(totals["ac_fixed_income"]).toBeCloseTo(0.15, 12);
    expect(totals["root"]).toBeCloseTo(0.75, 12);
    for (const ac of t.root.children) {
      const leaves = ac.children.flatMap((s) => s.children).reduce((s, i) => s + i.weight, 0);
      expect(totals[ac.id]).toBeCloseTo(leaves, 12);
      for (const sub of ac.children) {
        expect(totals[sub.id]).toBeCloseTo(sub.children.reduce((s, i) => s + i.weight, 0), 12);
      }
    }
    expect(totals["root"]).toBeCloseTo(totalWeight(t), 12);
  });

  it("an instrument total is its own weight, and an empty tree rolls up to 0", () => {
    let t = build();
    const id = idOf(t, "fi_tips");
    t = setWeight(t, id, 0.5);
    expect(rollUp(t)[id]).toBe(0.5);
    expect(rollUp(emptyTree("E"))).toEqual({ root: 0 });
  });
});

describe("normalise", () => {
  it("scales the weights to add up to 100%", () => {
    let t = build();
    const [a, b, c] = instruments(t);
    t = setWeight(t, a!.id, 0.2);
    t = setWeight(t, b!.id, 0.2);
    t = setWeight(t, c!.id, 0.1);
    const n = normalise(t);
    expect(totalWeight(n)).toBeCloseTo(1, 12);
    expect(instruments(n).map((i) => i.weight)).toEqual([0.4, 0.4, 0.2].map((x) => expect.closeTo(x, 12)));
    expect(validate(n).errors).toEqual([]);
    expect(validate(n).notices).toEqual([]);
  });

  it("also scales down a total above 100%", () => {
    let t = build();
    const [a, b] = instruments(t);
    t = setWeight(t, a!.id, 0.9);
    t = setWeight(t, b!.id, 0.9);
    expect(totalWeight(normalise(t))).toBeCloseTo(1, 12);
  });

  it("returns a tree with no weight as is", () => {
    const t = build();
    expect(normalise(t)).toBe(t);
  });
});

describe("remainderToCash", () => {
  it("adds the USD cash line and puts the remainder in it", () => {
    let t = build();
    t = setWeight(t, idOf(t, "eq_global"), 0.6);
    const out = remainderToCash(t, LIB);
    expect(totalWeight(out)).toBeCloseTo(1, 12);
    const cash = instruments(out).find((i) => i.kind === "cash")!;
    expect(cash.weight).toBeCloseTo(0.4, 12);
    expect(out.root.children[0]!.label).toBe("Equities");
    expect(out.root.children.at(-1)!.label).toBe("Cash");
    expect(validate(out)).toEqual({ errors: [], notices: [] });
  });

  it("adds to the cash that is already there", () => {
    let t = addLine(build(), line("cash_usd"));
    t = setWeight(t, idOf(t, "cash_usd"), 0.1);
    t = setWeight(t, idOf(t, "eq_global"), 0.5);
    const out = remainderToCash(t, LIB);
    expect(instruments(out).find((i) => i.kind === "cash")!.weight).toBeCloseTo(0.5, 12);
    expect(instruments(out)).toHaveLength(instruments(t).length);
  });

  it("returns a tree at 100% as is", () => {
    let t = build();
    t = setWeight(t, idOf(t, "eq_global"), 1);
    expect(remainderToCash(t, LIB)).toBe(t);
  });

  it("returns the tree as is when the library has no USD cash line", () => {
    const t = build();
    expect(remainderToCash(t, LIB.filter((l) => l.id !== USD_CASH_LIBRARY_ID))).toBe(t);
  });
});

describe("validate", () => {
  it("accepts a tree at exactly 100% without a notice", () => {
    let t = build();
    t = setWeight(t, idOf(t, "eq_global"), 0.6);
    t = setWeight(t, idOf(t, "fi_tips"), 0.4);
    expect(validate(t)).toEqual({ errors: [], notices: [] });
  });

  it("accepts a total within float tolerance of 100%", () => {
    let t = build();
    const ids = instruments(t).map((i) => i.id);
    t = setWeight(t, ids[0]!, 0.1);
    t = setWeight(t, ids[1]!, 0.2);
    t = setWeight(t, ids[2]!, 0.7);
    expect(validate(t)).toEqual({ errors: [], notices: [] });
  });

  it("gives a notice for the remainder that goes to USD cash", () => {
    let t = build();
    t = setWeight(t, idOf(t, "eq_global"), 0.6);
    expect(validate(t)).toEqual({
      errors: [],
      notices: ["40.00% is not allocated; it is held in USD cash."],
    });
    expect(remainder(t)).toBeCloseTo(0.4, 12);
  });

  it("refuses a negative weight and a total above 100%", () => {
    let t = build();
    const [a, b] = instruments(t);
    t = setWeight(t, a!.id, -0.1);
    expect(validate(t).errors.join()).toContain("must be 0 or more");
    t = setWeight(setWeight(t, a!.id, 0.7), b!.id, 0.4);
    expect(validate(t).errors).toEqual(["the weights add up to 110.00%, which is more than 100%"]);
  });

  it("refuses a weight on a row with no proxy but allows it at 0", () => {
    let t = addLine(emptyTree("T"), line("alt_vc"));
    const id = idOf(t, "alt_vc");
    expect(validate(t).errors).toEqual([]);
    t = setWeight(t, id, 0.1);
    expect(validate(t).errors.join()).toContain("has no proxy yet");
    expect(validate(swapInstrument(t, id, "PSP")).errors).toEqual([]);
  });

  it("refuses more than 50 instruments", () => {
    let t = build();
    const subId = "sub_eq_global";
    while (instruments(t).length < MAX_INSTRUMENTS) t = addInstrument(t, subId, "VT");
    expect(validate(t).errors).toEqual([]);
    t = addInstrument(t, subId, "VT");
    expect(validate(t).errors).toEqual(["at most 50 instruments are allowed, got 51"]);
  });

  it("allows the same ticker in two lines", () => {
    let t = build();
    t = swapInstrument(t, idOf(t, "eq_global"), "SPY");
    t = swapInstrument(t, idOf(t, "eq_na_large"), "SPY");
    t = setWeight(setWeight(t, idOf(t, "eq_global"), 0.3), idOf(t, "eq_na_large"), 0.3);
    expect(validate(t).errors).toEqual([]);
  });

  it("refuses a ticker on cash, a bad ticker, a repeated id and a bad cost", () => {
    let t = addLine(emptyTree("T"), line("cash_usd"));
    const id = idOf(t, "cash_usd");
    const cash = { ...instruments(t)[0]!, ticker: "BIL" };
    t = { ...t, root: { ...t.root, children: [{ ...t.root.children[0]!, children: [{ ...t.root.children[0]!.children[0]!, children: [cash, { ...cash, ticker: "bad ticker!", kind: "holding" as const }] }] }] } };
    const errors = validate(t).errors.join("|");
    expect(errors).toContain(`cash instrument "${id}" cannot have a ticker`);
    expect(errors).toContain("has an invalid ticker");
    expect(errors).toContain("is used twice");
    expect(validate({ ...build(), cost_bps: -1 }).errors.join()).toContain("cost_bps");
    expect(validate({ ...build(), cost_bps: 1000.5 }).errors.join()).toContain("cost_bps");
  });
});
