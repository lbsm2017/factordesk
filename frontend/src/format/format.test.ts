import { describe, expect, it } from "vitest";
import { dateLong, dateShort, isIsoDate, MINUS, num, parseIsoDate, pct, pval, signed, tstat } from "./index";

describe("numbers", () => {
  it("uses the true minus sign U+2212 and never a hyphen", () => {
    expect(MINUS).toBe("−");
    expect(signed(-0.141)).toBe("−0.141");
    expect(signed(-0.141)).not.toContain("-");
    expect(num(-1234.5, 1)).toBe("−1,234.5");
  });

  it("puts + on positive signed values and prints zero unsigned", () => {
    expect(signed(0.998)).toBe("+0.998");
    expect(signed(0)).toBe("0.000");
    expect(signed(-0)).toBe("0.000");
    expect(signed(0.0001)).toBe("0.000");
    expect(signed(-0.0001)).toBe("0.000");
    expect(num(-0.0001)).toBe("0.000");
  });

  it("groups thousands", () => {
    expect(num(1234567.891, 2)).toBe("1,234,567.89");
    expect(signed(12345.6, 1)).toBe("+12,345.6");
  });

  it("formats percent from decimals", () => {
    expect(pct(0.0081)).toBe("+0.81%");
    expect(pct(-0.0081)).toBe("−0.81%");
    expect(pct(0.1264, 2, false)).toBe("12.64%");
    expect(pct(0)).toBe("0.00%");
    expect(pct(0.1264, 1, false)).toBe("12.6%");
  });

  it("formats t statistics and p values", () => {
    expect(tstat(475.3)).toBe("475");
    expect(tstat(-13.84)).toBe("−13.8");
    expect(tstat(2.24)).toBe("2.2");
    expect(pval(0.0004)).toBe("<0.001");
    expect(pval(0.0312)).toBe("0.031");
  });
});

describe("dates", () => {
  it("writes long dates from a fixed month table", () => {
    expect(dateLong("2024-08-08")).toBe("8 Aug 2024");
    expect(dateLong("2026-09-30")).toBe("30 Sep 2026");
    expect(dateLong("2026-01-01")).toBe("1 Jan 2026");
  });

  it("writes month and year", () => {
    expect(dateShort("2024-08-08")).toBe("Aug 2024");
  });

  it("parses only real calendar dates", () => {
    expect(parseIsoDate("2024-02-29")).toEqual({ year: 2024, month: 2, day: 29 });
    expect(isIsoDate("2025-02-29")).toBe(false);
    expect(isIsoDate("2025-13-01")).toBe(false);
    expect(isIsoDate("2025-1-1")).toBe(false);
    expect(isIsoDate("")).toBe(false);
  });

  it("rejects a bad date instead of printing nonsense", () => {
    expect(() => dateLong("not a date")).toThrow(RangeError);
  });
});
