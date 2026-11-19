import { describe, expect, it } from "vitest";
import type { FactorStat } from "../api/types";
import { mockReport } from "../test/fixture";
import { exposureReading, plainName, tagText, WARN_PLAIN, warningSummary } from "./plain";

describe("plain text", () => {
  it("words estimate tags as significant or not significant", () => {
    expect(tagText("reliable")).toBe("significant");
    expect(tagText("noise")).toBe("not significant");
    expect(tagText(null)).toBe("n/a");
  });

  it("names factors in plain words", () => {
    expect(plainName("Mkt-RF")).toBe("Market");
    expect(plainName("XYZ")).toBe("XYZ");
  });

  it("uses the plain warning text, and falls back to the message for unknown codes", () => {
    const known = { code: "short_history", message: "n = 300" };
    const unknown = { code: "something_new", message: "Raw message." };
    expect(warningSummary([known])).toBe("The history is short, so the betas rest on a small sample.");
    expect(warningSummary([unknown])).toBe("Raw message.");
    expect(warningSummary([known, unknown, unknown])).toBe(
      "The history is short, so the betas rest on a small sample. Raw message.",
    );
  });

  it("has plain text for every warning code the backend emits", () => {
    const codes = ["residual_reversal", "short_history", "collinearity", "audit_errors", "audit_warnings", "factor_data_lag"];
    for (const code of codes) {
      const text = warningSummary([{ code, message: "Raw message." }]);
      expect(text, code).toBe(WARN_PLAIN[code]);
      expect(text, code).not.toBe("Raw message.");
      expect(text.endsWith("."), code).toBe(true);
    }
    expect(Object.keys(WARN_PLAIN).sort()).toEqual([...codes].sort());
  });

  it("says residual volatility is overstated, not understated, when the gate fires (N1, M3.6)", () => {
    expect(WARN_PLAIN.residual_reversal).toBe(
      "Prices look out of step with the factor data, so R² is probably understated and residual volatility overstated.",
    );
    expect(WARN_PLAIN.residual_reversal).not.toMatch(/volatility are probably understated/);
  });

  it("words the audit-error summary like the static report (F4)", () => {
    expect(WARN_PLAIN.audit_errors).toBe(
      "The price audit found errors, so the headline numbers are not interpretable until they are explained; see Data and audit.",
    );
  });

  it("reads the exposures from the tags", () => {
    const text = exposureReading(mockReport.regression.factors);
    expect(text.startsWith("Over this window the stock ")).toBe(true);
    expect(text).toContain("market");
    expect(text.endsWith(".")).toBe(true);
  });

  it("says there is no clear tilt when nothing is reliable", () => {
    const noise = mockReport.regression.factors.map((f) => ({ ...f, tag: "noise" as const }));
    expect(exposureReading(noise)).toBe(
      "There is no clear tilt to market (Mkt-RF), size (SMB), value (HML), profitability (RMW) or investment (CMA).",
    );
  });

  it("mentions a style lean by one rule for every factor: significant and not negligible", () => {
    const base = mockReport.regression.factors[0] as FactorStat;
    const make = (name: string, beta: number): FactorStat => ({ ...base, name, beta, tag: "reliable" });
    const text = exposureReading([make("Mkt-RF", 1.008), make("SMB", -0.148), make("CMA", 0.01), make("Mom", -0.012)]);
    expect(text).toContain("leans toward large companies (SMB -0.148)".replace("-", "−"));
    expect(text).not.toContain("recent losers");
    expect(text).not.toContain("CMA +0.010");
    expect(text).toContain("There is no clear tilt to investment (CMA) or momentum (Mom).");
    expect(exposureReading([make("Mom", -0.2)])).toBe("Over this window the stock leans toward recent losers (Mom −0.200).");
    expect(exposureReading([make("Mom", 0.2)])).toContain("recent winners (Mom +0.200)");
  });
});
