import { describe, expect, it } from "vitest";
import { mockReport } from "../test/fixture";
import { exposureReading, plainName, warningSummary } from "./plain";

describe("plain text", () => {
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
});
