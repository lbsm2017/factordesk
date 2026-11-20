import { describe, expect, it } from "vitest";
import { downloadHref, portfolioBody, reportParams, uploadBody } from "./queries";
import { currencyOf, hedgeFlags, reportCurrency } from "./currency";
import { EMPTY_URL_STATE } from "../state/url";
import { mockReport } from "../test/fixture";
import { buildPreset } from "../portfolio/presets";
import { LIBRARY } from "../portfolio/testLibrary";

const spy = { ...EMPTY_URL_STATE, ticker: "SPY", range: "3Y" as const };

describe("requests carry the reference currency", () => {
  it("adds ccy=EUR to the ticker query and the download link in the euro view only", () => {
    expect(reportParams(spy, "EUR")).toEqual({ range: "3Y", model: "ff6", ccy: "EUR" });
    expect(reportParams({ ...spy, range: null, start: "2023-01-02" }, "EUR")).toEqual({
      start: "2023-01-02",
      model: "ff6",
      ccy: "EUR",
    });
    expect(downloadHref(spy, "EUR")).toBe("/api/report/SPY/html?range=3Y&model=ff6&ccy=EUR");
    // USD is the API default: the request stays as it was.
    expect(reportParams(spy, "USD")).toEqual({ range: "3Y", model: "ff6" });
    expect(reportParams(spy)).toEqual({ range: "3Y", model: "ff6" });
    expect(downloadHref(spy)).toBe("/api/report/SPY/html?range=3Y&model=ff6");
  });

  it("falls back to the ccy of the URL state when no currency is passed", () => {
    expect(reportParams({ ...spy, ccy: "EUR" })).toEqual({ range: "3Y", model: "ff6", ccy: "EUR" });
  });

  it("sends the record's currency always and ccy=EUR in the euro view of an upload", () => {
    const file = new File(["date,return\n"], "r.csv");
    const usd = uploadBody({ file, name: "", grossNet: "" });
    expect(usd.get("record_currency")).toBe("USD");
    expect(usd.has("ccy")).toBe(false);
    const eur = uploadBody({ file, name: "", grossNet: "", recordCurrency: "EUR", ccy: "EUR" });
    expect(eur.get("record_currency")).toBe("EUR");
    expect(eur.get("ccy")).toBe("EUR");
    const mixed = uploadBody({ file, name: "", grossNet: "", recordCurrency: "EUR", ccy: "USD" });
    expect(mixed.get("record_currency")).toBe("EUR");
    expect(mixed.has("ccy")).toBe(false);
  });

  it("puts reference_currency in the portfolio body in the euro view only", () => {
    const tree = buildPreset("6040", "Mine", LIBRARY);
    const base = { model: "ff6" as const, range: "10Y", start: null, end: null };
    expect(portfolioBody({ tree, ...base, currency: "EUR" })).toEqual({ ...tree, reference_currency: "EUR" });
    expect(portfolioBody({ tree, ...base, currency: "USD" })).toBe(tree);
    expect(portfolioBody({ tree, ...base })).toBe(tree);
  });
});

describe("reading the currency fields of a report and a library line", () => {
  it("reads currency.reference, and treats an absent block as USD", () => {
    expect(currencyOf(mockReport)).toBeNull();
    expect(reportCurrency(mockReport)).toBe("USD");
    const eur = { ...mockReport, currency: { reference: "EUR", fx_source: "a", rate_source: "b", notes: [] } };
    expect(reportCurrency(eur as typeof mockReport)).toBe("EUR");
    expect(currencyOf({ ...mockReport, currency: { reference: "JPY" } } as unknown as typeof mockReport)).toBeNull();
  });

  it("reads the optional hedge booleans", () => {
    const line = LIBRARY[0];
    if (line === undefined) throw new Error("no library line");
    expect(hedgeFlags(line)).toEqual({ hedgeEur: false, multiCurrency: false });
    expect(hedgeFlags({ ...line, hedge_eur: true } as typeof line)).toEqual({ hedgeEur: true, multiCurrency: false });
    expect(hedgeFlags({ ...line, multi_currency: true } as typeof line)).toEqual({ hedgeEur: false, multiCurrency: true });
    expect(hedgeFlags(undefined)).toEqual({ hedgeEur: false, multiCurrency: false });
  });
});
