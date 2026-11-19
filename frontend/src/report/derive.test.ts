import { describe, expect, it } from "vitest";
import { cloneReport, mockReport } from "../test/fixture";
import {
  betaStats,
  dateTicks,
  derivedStats,
  factorOrder,
  firstFullWindow,
  isoMs,
  niceDomain,
  quantile,
  rollingPoints,
  sci,
  slotOf,
  windowStats,
} from "./derive";

const w252 = mockReport.rolling.find((w) => w.window === 252)!;
const w126 = mockReport.rolling.find((w) => w.window === 126)!;

describe("derived rolling statistics against average_beta", () => {
  it("matches the report's own mean, spread, extremes and share above zero within 1e-5", () => {
    expect(mockReport.average_beta.window).toBe(252);
    for (const a of mockReport.average_beta.factors) {
      const d = derivedStats(w252, a.name);
      expect(d, a.name).not.toBeNull();
      expect(d!.n).toBe(mockReport.average_beta.n_stamps);
      expect(Math.abs(d!.mean - (a.mean as number)), `${a.name} mean`).toBeLessThan(1e-5);
      expect(Math.abs(d!.sd - (a.sd as number)), `${a.name} sd`).toBeLessThan(1e-5);
      expect(Math.abs(d!.min - (a.min as number)), `${a.name} min`).toBeLessThan(1e-5);
      expect(Math.abs(d!.max - (a.max as number)), `${a.name} max`).toBeLessThan(1e-5);
      expect(Math.abs(d!.shareAbove - (a.share_positive as number)), `${a.name} share`).toBeLessThan(1e-5);
    }
  });

  it("matches the middle 80% to the precision of the mock (it carries four decimals and a looser quantile)", () => {
    for (const a of mockReport.average_beta.factors) {
      const d = derivedStats(w252, a.name)!;
      expect(Math.abs(d.p10 - (a.p10 as number)), `${a.name} p10`).toBeLessThan(5e-4);
      expect(Math.abs(d.p90 - (a.p90 as number)), `${a.name} p90`).toBeLessThan(5e-4);
    }
  });

  it("uses the report's numbers for the primary window and derived ones for the other", () => {
    const mkt = mockReport.average_beta.factors.find((f) => f.name === "Mkt-RF")!;
    const primary = windowStats(mockReport, w252, "Mkt-RF")!;
    expect(primary.p10).toBe(mkt.p10);
    expect(primary.p90).toBe(mkt.p90);
    const other = windowStats(mockReport, w126, "Mkt-RF")!;
    expect(other.p10).toBeCloseTo(derivedStats(w126, "Mkt-RF")!.p10, 12);
    expect(other.n).toBeGreaterThan(primary.n);
  });

  it("falls back to the derived numbers when average_beta is not ok", () => {
    const report = cloneReport();
    report.average_beta = { ...report.average_beta, status: "insufficient_data", reason: "x", factors: [] } as never;
    const w = report.rolling.find((x) => x.window === 252)!;
    expect(windowStats(report, w, "SMB")).toEqual(derivedStats(w, "SMB"));
  });
});

describe("betaStats", () => {
  it("summarises a small series by hand", () => {
    const s = betaStats([-1, 0, 1, 2, 3])!;
    expect(s).toMatchObject({ n: 5, latest: 3, mean: 1, min: -1, max: 3, shareAbove: 0.6 });
    expect(s.sd).toBeCloseTo(Math.sqrt(2.5), 12);
    expect(s.p10).toBeCloseTo(-0.6, 12);
    expect(s.p90).toBeCloseTo(2.6, 12);
  });

  it("returns null for an empty series", () => {
    expect(betaStats([])).toBeNull();
  });

  it("quantile interpolates linearly like numpy", () => {
    expect(quantile([1, 2, 3, 4], 0.5)).toBe(2.5);
    expect(quantile([4, 1, 3, 2], 0.25)).toBeCloseTo(1.75, 12);
    expect(quantile([7], 0.9)).toBe(7);
  });
});

describe("rolling points", () => {
  it("drops warm-up stamps and stamps without a standard error", () => {
    const pts = rollingPoints(w126, "Mkt-RF");
    expect(pts[0]?.index).toBe(125);
    expect(pts).toHaveLength(w126.dates.length - 125);
    expect(firstFullWindow(w126, factorOrder(mockReport))).toBe(w126.dates[125]);
    expect(firstFullWindow(w252, ["Nope"])).toBeNull();
  });
});

describe("scales and ticks", () => {
  it("gives a round domain with its ticks", () => {
    // The static report's domain for the return panel: one step of room below zero.
    const r = niceDomain(0, 0.1264, 5);
    expect(r.lo).toBeCloseTo(-0.05, 12);
    expect(r.hi).toBeCloseTo(0.15, 12);
    expect(r.ticks).toEqual([-0.05, 0, 0.05, 0.1, 0.15]);
    const d = niceDomain(-0.0002, 0.9941, 4);
    expect(d.lo).toBeLessThanOrEqual(-0.0002);
    expect(d.hi).toBeGreaterThanOrEqual(0.9941);
    expect(d.ticks).toContain(0);
  });

  it("widens a flat range", () => {
    const d = niceDomain(1, 1);
    expect(d.lo).toBeLessThan(1);
    expect(d.hi).toBeGreaterThan(1);
  });

  it("makes yearly ticks for a long span and quarterly ticks for a short one", () => {
    const long = dateTicks(isoMs("2015-03-10"), isoMs("2026-09-30"));
    expect(long.map((t) => t.label)).toEqual(expect.arrayContaining(["2016", "2020", "2026"]));
    const short = dateTicks(isoMs("2025-07-28"), isoMs("2026-09-30"));
    expect(short.map((t) => t.label)).toEqual(["Oct 2025", "Jan 2026", "Apr 2026", "Jul 2026"]);
    expect(short.filter((t) => t.january).map((t) => t.label)).toEqual(["Jan 2026"]);
  });

  it("rejects a malformed date", () => {
    expect(() => isoMs("2026-13-01")).toThrow(RangeError);
  });
});

describe("factor helpers", () => {
  it("uses canonical colour slots and falls back to order of appearance", () => {
    expect(slotOf("HML", ["Mkt-RF", "SMB", "HML"])).toBe(3);
    expect(slotOf("Mom", ["A", "Mom"])).toBe(6);
    expect(slotOf("UMD", ["A", "UMD"])).toBe(2);
    expect(slotOf("Unknown", [])).toBe(1);
  });

  it("prints scientific notation with a two-digit exponent", () => {
    expect(sci(0)).toBe("0.0e+00");
    expect(sci(1.2e-17)).toBe("1.2e-17");
    expect(sci(3e5)).toBe("3.0e+05");
  });
});
