import { describe, expect, it } from "vitest";
import { buildPreset } from "../portfolio/presets";
import { LIBRARY } from "../portfolio/testLibrary";
import { EMPTY_URL_STATE } from "../state/url";
import { downloadHref, portfolioBody, reportParams, reportQueryKey, uploadBody } from "./queries";

const spy = { ...EMPTY_URL_STATE, ticker: "SPY", range: "3Y" as const };
const europe = { ...spy, fs: "europe" as const };

describe("requests carry the factor set", () => {
  it("adds factor_set=europe to the ticker query and the download link, for the Europe set only", () => {
    expect(reportParams(europe)).toEqual({ range: "3Y", model: "ff6", factor_set: "europe" });
    expect(reportParams(europe, "EUR")).toEqual({ range: "3Y", model: "ff6", ccy: "EUR", factor_set: "europe" });
    expect(reportParams({ ...europe, range: null, start: "2023-01-02" })).toEqual({
      start: "2023-01-02",
      model: "ff6",
      factor_set: "europe",
    });
    expect(downloadHref(europe)).toBe("/api/report/SPY/html?range=3Y&model=ff6&factor_set=europe");
    // The US set is the API default: the request stays as it was.
    expect(reportParams(spy)).toEqual({ range: "3Y", model: "ff6" });
    expect(downloadHref(spy)).toBe("/api/report/SPY/html?range=3Y&model=ff6");
  });

  it("keeps the two sets apart in the query key", () => {
    expect(reportQueryKey(spy)).not.toEqual(reportQueryKey(europe));
    expect(reportQueryKey(europe).at(-1)).toBe("europe");
  });

  it("sends factor_set in the upload form for the Europe set only", () => {
    const file = new File(["date,return\n"], "r.csv");
    expect(uploadBody({ file, name: "", grossNet: "", factorSet: "europe" }).get("factor_set")).toBe("europe");
    expect(uploadBody({ file, name: "", grossNet: "", factorSet: "us" }).has("factor_set")).toBe(false);
    expect(uploadBody({ file, name: "", grossNet: "" }).has("factor_set")).toBe(false);
  });

  it("puts factor_set in the portfolio body for the Europe set only, beside reference_currency", () => {
    const tree = buildPreset("6040", "Mine", LIBRARY);
    const base = { model: "ff6" as const, range: "10Y", start: null, end: null };
    expect(portfolioBody({ tree, ...base, factorSet: "europe" })).toEqual({ ...tree, factor_set: "europe" });
    expect(portfolioBody({ tree, ...base, factorSet: "europe", currency: "EUR" })).toEqual({
      ...tree,
      reference_currency: "EUR",
      factor_set: "europe",
    });
    expect(portfolioBody({ tree, ...base, factorSet: "us" })).toBe(tree);
  });
});
