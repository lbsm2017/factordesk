import { describe, expect, it } from "vitest";
import type { FactorStat } from "../api/types";
import { cloneReport, mockReport } from "../test/fixture";
import { withSection } from "../test/sectionFixtures";
import {
  dataOutcome,
  exposuresOutcome,
  priceOutcome,
  regressionOutcome,
  returnsOutcome,
  riskOutcome,
  rollingOutcome,
} from "./outcome";
import { drawdownOutcome, worldBetaOutcome } from "./outcomeDeep";

const withPerformance = () => withSection(cloneReport(), "performance");
const withWorld = () => withSection(cloneReport(), "world_beta");

function priceIndex(r: ReturnType<typeof cloneReport>, date: string): number {
  return r.price_series.dates.indexOf(date);
}

describe("outcome lines of DV4.9 on the mock report", () => {
  it("Price: the change over the analysed range and the uncharted tail", () => {
    expect(priceOutcome(mockReport)).toBe(
      "With dividends reinvested, SPY rose 30.5% over the analysed range (8 Aug 2024 to 30 Sep 2026). The last 32 price days are charted but not analysed.",
    );
  });

  it("Price: fell, ended where it started, a single uncharted day, and no line when a price is missing", () => {
    const fell = cloneReport();
    const start = fell.price_series.adj_close[priceIndex(fell, fell.data.actual_start)] as number;
    fell.price_series.adj_close[priceIndex(fell, fell.data.actual_end)] = start * 0.9;
    fell.data.uncovered.n = 1;
    expect(priceOutcome(fell)).toBe(
      "With dividends reinvested, SPY fell 10.0% over the analysed range (8 Aug 2024 to 30 Sep 2026). The last 1 price day is charted but not analysed.",
    );
    const flat = cloneReport();
    const base = flat.price_series.adj_close[priceIndex(flat, flat.data.actual_start)] as number;
    flat.price_series.adj_close[priceIndex(flat, flat.data.actual_end)] = base;
    flat.data.uncovered.n = 0;
    expect(priceOutcome(flat)).toBe(
      "With dividends reinvested, SPY ended where it started over the analysed range (8 Aug 2024 to 30 Sep 2026).",
    );
    const gone = cloneReport();
    gone.price_series.adj_close[priceIndex(gone, gone.data.actual_end)] = null;
    expect(priceOutcome(gone)).toBeNull();
  });

  it("Drawdown: growth, largest fall and recovery", () => {
    const r = withPerformance();
    const p = r.performance;
    if (!p) throw new Error("fixture");
    expect(drawdownOutcome(r, p)).toBe(
      "SPY shrank 7.2% a year over the analysed range; its largest fall was 41.0%, from 2 Jan 2025 to 12 Mar 2026, and it had not recovered by 30 Sep 2026.",
    );
    if (p.drawdown) p.drawdown.recovery_date = "2026-08-03";
    expect(drawdownOutcome(r, p)).toContain("and it was back at the peak by 3 Aug 2026.");
    if (p.returns) p.returns.cagr = 0.05;
    expect(drawdownOutcome(r, p)).toContain("SPY grew 5.0% a year");
    if (p.returns) p.returns.cagr = 0;
    expect(drawdownOutcome(r, p)).toContain("SPY was flat over the analysed range");
  });

  it("Factor exposures: how many are clear and which", () => {
    expect(exposuresOutcome(mockReport)).toBe(
      "Three of the five exposures are clear (market, size and profitability); value and investment are not distinguishable from zero.",
    );
    const none = cloneReport();
    for (const f of none.regression.factors) f.tag = "noise";
    expect(exposuresOutcome(none)).toBe("None of the five exposures is distinguishable from zero over this range.");
    const all = cloneReport();
    for (const f of all.regression.factors) f.tag = "reliable";
    expect(exposuresOutcome(all)).toBe(
      "Five of the five exposures are clear (market, size, value, profitability and investment).",
    );
    const one = cloneReport();
    for (const f of one.regression.factors) f.tag = f.name === "Mkt-RF" ? "reliable" : "noise";
    expect(exposuresOutcome(one)).toBe(
      "One of the five exposures is clear (market); size, value, profitability and investment are not distinguishable from zero.",
    );
  });

  it("World beta: the beta against the world next to the US market beta on the same days", () => {
    expect(worldBetaOutcome(withWorld())).toBe(
      "Against world stocks, SPY's beta was 0.93 over 8 Aug 2024 to 30 Sep 2026 (540 days), about the same as its beta against the US market on the same days (1.00).",
    );
  });

  it("World beta: apart intervals say lower; a shorter span names the fund's start or the overlap", () => {
    const apart = withWorld();
    const s = apart.world_beta;
    if (!s?.world) throw new Error("fixture");
    Object.assign(s.world, { beta: 0.7, ci_low: 0.6, ci_high: 0.8 });
    expect(worldBetaOutcome(apart)).toContain("beta was 0.70 over");
    expect(worldBetaOutcome(apart)).toContain(", lower than its beta against the US market");
    s.sample.start = "2024-09-03";
    s.acwi_first_date = "2024-08-30";
    expect(worldBetaOutcome(apart)).toContain(
      "This covers a shorter span than the five-factor model, because the fund's history starts in August 2024.",
    );
    s.acwi_first_date = "2023-01-03";
    expect(worldBetaOutcome(apart)).toContain("because the two price histories overlap only from 3 Sep 2024.");
    s.status = "failed";
    expect(worldBetaOutcome(apart)).toBeNull();
  });

  it("Return sources: the largest source, with the hedge for a source that is not clear", () => {
    expect(returnsOutcome(mockReport)).toBe(
      "Market exposure accounts for most of the 12.6% a year SPY earned above cash (+11.6%).",
    );
    const r = cloneReport();
    for (const f of r.regression.factors) if (f.name === "Mkt-RF") f.tag = "noise";
    expect(returnsOutcome(r)).toBe(
      "Market exposure accounts for most of the 12.6% a year SPY earned above cash (+11.6%), but that exposure is not distinguishable from zero.",
    );
    const spread = cloneReport();
    spread.return_contribution.total_annualised_mean_excess_return = -0.3;
    expect(returnsOutcome(spread)).toBe(
      "No single source accounts for most of the 30.0% a year SPY earned below cash; the largest is market exposure (+11.6%).",
    );
    const alpha = cloneReport();
    alpha.return_contribution.alpha = 0.5;
    alpha.regression.alpha_tag = "noise";
    expect(returnsOutcome(alpha)).toBe(
      "The return beyond its exposures accounts for most of the 12.6% a year SPY earned above cash (+50.0%), and it is not distinguishable from zero.",
    );
  });

  it("Risk sources: the largest share, or stock-specific risk when it leads", () => {
    expect(riskOutcome(mockReport)).toBe("Market exposure drives 99.4% of SPY's day-to-day risk; 0.5% is specific to SPY.");
    const idio = cloneReport();
    idio.risk_contribution.order = ["Idiosyncratic", ...idio.risk_contribution.order.filter((n) => n !== "Idiosyncratic")];
    expect(riskOutcome(idio)).toBe("Most of SPY's day-to-day risk is specific to SPY (0.5%).");
  });

  it("Exposure over time: the middle 80% of the market beta and the factors on both sides of zero", () => {
    expect(rollingOutcome(mockReport, 252)).toBe(
      "In 80% of the 252-day windows the market beta was between 0.99 and 1.01. The value, profitability and investment exposures spent long stretches on both sides of zero.",
    );
    expect(rollingOutcome(mockReport, 7)).toBeNull();
  });

  it("Data and audit: the audit result and the days analysed", () => {
    expect(dataOutcome(mockReport)).toBe(
      "The price audit flagged 1 unusual item; none stops the analysis. 559 trading days analysed, 1 excluded.",
    );
    const clean = cloneReport();
    clean.data.audit_status = "clean";
    clean.data.audit_findings = [];
    clean.data.n_excluded = 0;
    expect(dataOutcome(clean)).toBe("The price audit found no problems. 559 trading days analysed, none excluded.");
    const bad = cloneReport();
    bad.data.audit_status = "errors";
    bad.data.audit_findings = bad.data.audit_findings.slice(0, 1).map((f) => ({ ...f, severity: "error" as const }));
    expect(dataOutcome(bad)).toBe(
      "The price audit found 1 error; the results above are not interpretable until it is explained. 559 trading days analysed, 1 excluded.",
    );
  });

  it("Regression detail: significant betas, the return beyond the exposures, and the gate sentence", () => {
    expect(regressionOutcome(mockReport)).toBe(
      "Three of the five betas are significant after allowing for testing five at once; the return beyond the exposures is not distinguishable from zero. Because the quality gate fired, a term counts as significant only when the 5-day estimate agrees.",
    );
    const r = cloneReport();
    r.quality_gate.fired = false;
    r.regression.alpha_tag = "reliable";
    expect(regressionOutcome(r)).toBe(
      "Three of the five betas are significant after allowing for testing five at once; the return beyond the exposures is distinguishable from zero.",
    );
  });

  it("Regression detail: counts the real number of betas under FF6", () => {
    const r = cloneReport();
    r.model = "ff6";
    const mom = { ...(r.regression.factors[0] as FactorStat), name: "Mom", beta: -0.2, tag: "reliable" as const };
    r.regression.factors = [...r.regression.factors, mom];
    const k = r.regression.factors.filter((f) => f.tag === "reliable").length;
    const text = regressionOutcome(r) as string;
    expect(text.startsWith(`${["None", "One", "Two", "Three", "Four", "Five", "Six"][k]} of the six betas`)).toBe(true);
    expect(text).toContain("after allowing for testing six at once");
    expect(text).not.toContain("five");
  });

  it("uses no forecast, causal or second-person words and never says no alpha", () => {
    const r = withSection(withSection(cloneReport(), "performance"), "world_beta");
    const lines = [
      priceOutcome(r),
      r.performance ? drawdownOutcome(r, r.performance) : null,
      exposuresOutcome(r),
      worldBetaOutcome(r),
      returnsOutcome(r),
      riskOutcome(r),
      rollingOutcome(r, 252),
      dataOutcome(r),
    ].join(" ");
    expect(lines).not.toMatch(/\b(will|expected|likely|because|driven by|causes?|your|no alpha)\b/i);
    expect(lines).not.toContain("—");
  });
});
