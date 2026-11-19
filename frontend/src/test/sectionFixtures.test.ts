import { describe, expect, it } from "vitest";
import { cloneReport, mockReport } from "./fixture";
import { SECTION_FIELDS, withSection } from "./sectionFixtures";

describe("schema v3 contract fixtures", () => {
  it("the mock report is version 4 with every optional section null", () => {
    expect(mockReport.schema_version).toBe("4");
    for (const field of SECTION_FIELDS) {
      expect(mockReport[field]).toBeNull();
    }
  });

  it("attaches each section fixture to a copy and leaves the original alone", () => {
    for (const field of SECTION_FIELDS) {
      const report = withSection(cloneReport(), field);
      const value = report[field];
      expect(value).not.toBeNull();
      const items = Array.isArray(value) ? value : [value];
      expect(items.length).toBeGreaterThan(0);
      for (const item of items) {
        expect(item).toHaveProperty("status");
        expect(item).toHaveProperty("reason");
        expect(item).toHaveProperty("sample");
      }
      expect(mockReport[field]).toBeNull();
    }
  });

  it("adds the footnote texts of the residual section, as the pipeline does", () => {
    expect(mockReport.label_text["L-INSAMPLE"]).toBeUndefined();
    const report = withSection(cloneReport(), "residual");
    for (const key of ["L-INSAMPLE", "L-PIT", "L-DESC-PIT", "L-HEDGE"]) {
      expect(report.label_text[key], key).toBeTruthy();
    }
    expect(report.label_text["L-VINTAGE"]).toBe(mockReport.label_text["L-VINTAGE"]);
  });
});
