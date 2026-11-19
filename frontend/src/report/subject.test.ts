import { describe, expect, it } from "vitest";
import { cloneReport, monthlyReport } from "../test/fixture";
import { hiddenPanels } from "./applicability";
import { auditWord, frequencyWord, isMonthly, isSubjectReport, observations, stepWord, subjectLine } from "./subject";

describe("subject wording", () => {
  it("leaves a ticker report in trading days", () => {
    const report = cloneReport();
    expect(isMonthly(report)).toBe(false);
    expect(isSubjectReport(report)).toBe(false);
    expect(observations(report, 1)).toBe("1 trading day");
    expect(observations(report, 1_200)).toBe("1,200 trading days");
    expect(auditWord(report)).toBe("price");
    expect(stepWord(report)).toBe("day-to-day");
    expect(frequencyWord(report)).toBe("daily");
    expect(subjectLine(report)).toBeNull();
    expect(hiddenPanels(report).size).toBe(0);
  });

  it("counts months for a monthly record", () => {
    expect(isMonthly(monthlyReport)).toBe(true);
    expect(isSubjectReport(monthlyReport)).toBe(true);
    expect(observations(monthlyReport, 1)).toBe("1 month");
    expect(observations(monthlyReport, 84)).toBe("84 months");
    expect(auditWord(monthlyReport)).toBe("data");
    expect(stepWord(monthlyReport)).toBe("month-to-month");
    expect(frequencyWord(monthlyReport)).toBe("monthly");
  });

  it("describes the record and its fee basis", () => {
    expect(subjectLine(monthlyReport)).toBe("Uploaded track record, returns after fees, in US dollars");
  });

  it("hides the rolling panel of a record because every window is not applicable", () => {
    expect(hiddenPanels(monthlyReport)).toEqual(new Set(["rolling"]));
  });

  it("keeps the rolling panel of a subject report that has usable windows", () => {
    const report = structuredClone(monthlyReport);
    const first = report.rolling[0];
    if (first === undefined) throw new Error("fixture has no rolling window");
    first.status = "ok";
    expect(hiddenPanels(report).size).toBe(0);
  });
});
