import { describe, expect, it } from "vitest";
import type { FactorReport } from "../api/types";
import { cloneReport, mockReport } from "../test/fixture";
import { withSection } from "../test/sectionFixtures";
import {
  alphaReading,
  betaReading,
  drawdownReading,
  marketPhrase,
  r2Reading,
  residualVolReading,
  sharpeReading,
  verdict,
  worldBetaReading,
} from "./verdict";

/** Words and phrases no generated sentence may contain (DV4.2: no forecast, no causation, no overclaim). */
const BANNED_PATTERNS: readonly RegExp[] = [
  /\bwill\b/i,
  /\bexpect/i,
  /\bshould\b/i,
  /\blikely\b/i,
  /\bforecast/i,
  /\bpredict/i,
  /\bbecause of\b/i,
  /\bdriven by\b/i,
  /\bcauses?\b/i,
  /\bmakes?\b/i,
  /\bno alpha\b/i,
  /\bno exposure\b/i,
  /\bnone\b/i,
  /!/,
];

/** Banned words found in `text` (empty when the text is clean). */
function bannedIn(text: string): string[] {
  return BANNED_PATTERNS.filter((re) => re.test(text)).map((re) => re.source);
}

const HEDGE =
  "Its closing prices look out of step with the factor data, so the share the model explains is probably understated.";

function edit(fn: (r: FactorReport) => void): FactorReport {
  const r = cloneReport();
  fn(r);
  return r;
}

function setFactor(r: FactorReport, name: string, patch: { beta?: number; tag?: "reliable" | "noise" | null }) {
  const f = r.regression.factors.find((x) => x.name === name);
  if (!f) throw new Error(name);
  Object.assign(f, patch);
}

describe("verdict (DV4.4, appendix A)", () => {
  it("A.1: the mock fixture, with the gate hedge", () => {
    const v = verdict(mockReport);
    expect(v.headline).toBe(
      "SPY moves with the market (about one-for-one), leans toward large companies and highly profitable firms, and shows no reliable return beyond its exposures.",
    );
    expect(v.hedge).toBe(HEDGE);
    expect(v.text).toBe(`${v.headline} ${HEDGE}`);
  });

  it("A.2: all five not significant", () => {
    const r = edit((x) => {
      for (const f of x.regression.factors) f.tag = "noise";
      x.quality_gate.fired = false;
    });
    const v = verdict(r);
    expect(v.headline).toBe(
      "SPY shows no reliable link to the market, has no clear tilt toward size, value, profitability or investment, and shows no reliable return beyond its exposures.",
    );
    expect(v.hedge).toBeNull();
  });

  it("A.3: audit errors drop the alpha part and the hedge", () => {
    const r = edit((x) => {
      x.data.audit_status = "errors";
      x.data.audit_findings.push({ code: "bad", severity: "error", message: "bad", dates: [] });
    });
    const v = verdict(r);
    expect(v.text).toBe(
      "The price audit found errors in SPY's prices, so these results are not interpretable until the errors are explained. Taken at face value, SPY moves with the market (about one-for-one) and leans toward large companies and highly profitable firms.",
    );
    expect(v.hedge).toBeNull();
  });

  it("A.4: a significant negative alpha", () => {
    const r = edit((x) => {
      x.regression.alpha_annual = -0.034;
      x.regression.alpha_tag = "reliable";
      x.quality_gate.fired = false;
    });
    expect(verdict(r).text).toBe(
      "SPY moves with the market (about one-for-one), leans toward large companies and highly profitable firms, and earned 3.4% a year less than its exposures explain over this range.",
    );
  });

  it("A.5: amplified market, growth tilt, significant positive alpha", () => {
    const r = edit((x) => {
      setFactor(x, "Mkt-RF", { beta: 1.42 });
      setFactor(x, "HML", { beta: -0.31, tag: "reliable" });
      x.regression.alpha_annual = 0.052;
      x.regression.alpha_tag = "reliable";
      x.quality_gate.fired = false;
    });
    const v = verdict(r);
    expect(v.text).toBe(
      "SPY amplifies market moves (about 1.42 times as much), leans toward large companies, growth stocks and highly profitable firms, and earned 5.2% a year more than its exposures explain over this range.",
    );
    expect(v.text.split(" ").length).toBe(32);
  });

  it("keeps the longest headline within 40 words by naming only the largest tilts", () => {
    const r = edit((x) => {
      setFactor(x, "Mkt-RF", { beta: -0.5 });
      setFactor(x, "SMB", { beta: 0.1, tag: "reliable" });
      setFactor(x, "HML", { beta: 0.4, tag: "reliable" });
      setFactor(x, "RMW", { beta: 0.3, tag: "reliable" });
      setFactor(x, "CMA", { beta: 0.2, tag: "reliable" });
      x.regression.alpha_annual = 0.05;
      x.regression.alpha_tag = "reliable";
      x.quality_gate.fired = false;
    });
    const v = verdict(r);
    expect(v.headline.split(" ").length).toBeLessThanOrEqual(40);
    expect(v.headline).toContain("leans toward value stocks and 3 other style tilts");
    expect(v.headline).toContain("tends to move against the market (about 0.50 times as much, in the opposite direction)");
  });

  it("says a failed fit in words and never claims a result", () => {
    const r = edit((x) => {
      x.regression.status = "insufficient_data";
      x.regression.reason = "Only 40 days of data.";
    });
    expect(verdict(r).text).toBe("factordesk could not fit the five-factor model for SPY over this range: Only 40 days of data.");
  });

  it("omits the market and alpha parts when their inputs are missing", () => {
    const r = edit((x) => {
      setFactor(x, "Mkt-RF", { tag: null });
      x.regression.alpha_annual = null;
      x.quality_gate.fired = false;
    });
    expect(verdict(r).headline).toBe("SPY leans toward large companies and highly profitable firms.");
  });
});

describe("market beta wording bands (DV4.2 item 6)", () => {
  it.each([
    [1.0, "moves with the market (about one-for-one)"],
    [0.91, "moves with the market (about one-for-one)"],
    [1.09, "moves with the market (about one-for-one)"],
    [1.1, "amplifies market moves (about 1.10 times as much)"],
    [0.9, "moves less than the market (about 0.90 times as much)"],
    [0.5, "moves less than the market (about 0.50 times as much)"],
    [-0.4, "tends to move against the market (about 0.40 times as much, in the opposite direction)"],
  ])("beta %s", (beta, text) => {
    expect(marketPhrase(beta, "reliable")).toBe(text);
  });

  it("is not claimed when the tag is not reliable, and missing when absent", () => {
    expect(marketPhrase(1.5, "noise")).toBe("shows no reliable link to the market");
    expect(marketPhrase(null, "reliable")).toBeNull();
    expect(marketPhrase(1, null)).toBeNull();
  });
});

describe("reading words", () => {
  it("come from the tags: clear evidence or could be noise", () => {
    expect(betaReading(mockReport, "Mkt-RF")).toMatchObject({ word: "Clear evidence", evidence: "clear" });
    expect(betaReading(mockReport, "HML")).toMatchObject({ word: "Could be noise", evidence: "noise" });
    expect(alphaReading(mockReport)).toMatchObject({ word: "Could be noise", evidence: "noise" });
    const sig = edit((x) => {
      x.regression.alpha_tag = "reliable";
    });
    expect(alphaReading(sig).word).toBe("Clear evidence");
  });

  it("carry no claim under audit errors", () => {
    const r = edit((x) => {
      x.data.audit_status = "errors";
    });
    expect(betaReading(r, "Mkt-RF").word).toBe("Unconfirmed");
    expect(alphaReading(r).word).toBe("Unconfirmed");
    expect(r2Reading(r).word).toBe("Unconfirmed");
  });

  it("hedge R-squared and residual volatility when the gate fired", () => {
    expect(r2Reading(mockReport).word).toBe("Probably understated");
    expect(residualVolReading(mockReport).word).toBe("Probably overstated");
    const r = edit((x) => {
      x.quality_gate.fired = false;
    });
    expect(r2Reading(r).word).toBe("Very high");
    expect(residualVolReading(r).word).toBe("Low");
  });

  it("hedge the Sharpe ratio when its interval includes zero", () => {
    const perf = withSection(mockReport, "performance").performance;
    expect(perf?.sharpe?.ci_includes_zero).toBe(true);
    expect(sharpeReading(perf?.sharpe ?? null)).toMatchObject({
      word: "Could be noise",
      note: "Cannot be told apart from zero.",
    });
    const above = { ...(perf?.sharpe as NonNullable<typeof perf>["sharpe"]), ci_includes_zero: false, ci95_low: 0.1 } as never;
    expect(sharpeReading(above).word).toBe("Clear evidence");
    expect(sharpeReading(null).word).toBe("–");
  });

  it("name the drawdown as recovered or not, with dates", () => {
    const perf = withSection(mockReport, "performance").performance;
    if (!perf) throw new Error("fixture");
    expect(drawdownReading(perf)).toMatchObject({ word: "Not recovered" });
    expect(drawdownReading(perf).note).toBe("From 2 Jan 2025 to 12 Mar 2026; not recovered by 30 Sep 2026");
    const back = structuredClone(perf);
    if (back.drawdown) back.drawdown.recovery_date = "2026-08-03";
    expect(drawdownReading(back)).toMatchObject({ word: "Recovered" });
  });

  it("read the ACWI beta from the section interval and comparison", () => {
    const r = withSection(mockReport, "world_beta");
    const wb = r.world_beta;
    if (!wb) throw new Error("fixture");
    expect(worldBetaReading(wb, r)).toMatchObject({ word: "Clear evidence", note: "lower than its one-factor US market beta of 1.00" });
  });
});

describe("banned words (DV4.2)", () => {
  it("flags forecast, causal and overclaiming words", () => {
    for (const bad of ["It will rise.", "We expect more.", "should return", "likely higher", "because of the market", "driven by size", "makes it rise", "no alpha", "none of it", "a forecast"]) {
      expect(bannedIn(bad), bad).not.toHaveLength(0);
    }
    expect(bannedIn("shows no reliable return beyond its exposures")).toEqual([]);
  });

  it("finds none in any generated sentence or reading", () => {
    const variants: FactorReport[] = [
      mockReport,
      edit((x) => {
        for (const f of x.regression.factors) f.tag = "noise";
      }),
      edit((x) => {
        x.data.audit_status = "errors";
      }),
      edit((x) => {
        x.regression.alpha_annual = -0.034;
        x.regression.alpha_tag = "reliable";
      }),
      edit((x) => {
        setFactor(x, "Mkt-RF", { beta: -0.4 });
        setFactor(x, "HML", { beta: -0.31, tag: "reliable" });
        setFactor(x, "CMA", { beta: 0.3, tag: "reliable" });
        x.regression.alpha_annual = 0.052;
        x.regression.alpha_tag = "reliable";
      }),
      edit((x) => {
        x.regression.status = "failed";
        x.regression.reason = "No data.";
      }),
    ];
    for (const r of variants) {
      const full = withSection(withSection(r, "performance"), "world_beta");
      const texts = [
        verdict(full).text,
        ...full.regression.factors.map((f) => betaReading(full, f.name).word),
        alphaReading(full).word,
        alphaReading(full).note ?? "",
        r2Reading(full).word,
        residualVolReading(full).word,
        sharpeReading(full.performance?.sharpe ?? null, full).word,
        sharpeReading(full.performance?.sharpe ?? null, full).note ?? "",
        full.performance ? (drawdownReading(full.performance).note ?? "") : "",
        full.world_beta ? (worldBetaReading(full.world_beta, full).note ?? "") : "",
      ];
      for (const t of texts) expect(bannedIn(t), t).toEqual([]);
    }
  });
});
