import { describe, expect, it } from "vitest";
import { earliestCommonStart, libraryById, lineCount, yearOf } from "./composer";
import { PRESETS, buildPreset } from "./presets";
import { LIBRARY } from "./testLibrary";
import { instruments, totalWeight, validate } from "./tree";

const BY_ID = libraryById(LIBRARY);

describe("presets", () => {
  it("offers Blank, 60/40, Balanced SAA and Growth, in that order", () => {
    expect(PRESETS.map((p) => p.label)).toEqual(["Blank", "60/40", "Balanced SAA", "Growth"]);
  });

  it("Blank has no lines", () => {
    const t = buildPreset("blank", "Mine", LIBRARY);
    expect(t.name).toBe("Mine");
    expect(lineCount(t)).toBe(0);
  });

  it("60/40 is IVV 60 and IEF 40", () => {
    const t = buildPreset("6040", "A", LIBRARY);
    expect(instruments(t).map((i) => [i.ticker, i.weight])).toEqual([
      ["IVV", 0.6],
      ["IEF", 0.4],
    ]);
  });

  it.each(["saa", "growth"] as const)("%s adds up to 100%, validates, and uses library proxies from before 2010", (id) => {
    const t = buildPreset(id, "A", LIBRARY);
    expect(totalWeight(t)).toBeCloseTo(1, 12);
    expect(validate(t).errors).toEqual([]);
    expect(lineCount(t)).toBe(PRESETS.find((p) => p.id === id)?.lines.length);
    for (const sub of t.root.children.flatMap((ac) => ac.children)) {
      const line = BY_ID.get(sub.library_id);
      expect(line, sub.library_id).toBeDefined();
      expect(line?.proxy, sub.library_id).not.toBeNull();
      expect(yearOf(line?.first_date), sub.library_id).toBeLessThan(2010);
    }
    expect(earliestCommonStart(t, BY_ID).date?.slice(0, 4)).toMatch(/^200\d$/);
  });

  it("leaves out a line the library does not have", () => {
    const t = buildPreset(
      "6040",
      "A",
      LIBRARY.filter((l) => l.id !== "fi_na_gov"),
    );
    expect(instruments(t).map((i) => i.ticker)).toEqual(["IVV"]);
  });
});
