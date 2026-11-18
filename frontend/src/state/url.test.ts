import { describe, expect, it } from "vitest";
import { applyPatch, checkTicker, EMPTY_URL_STATE, isSuggestQuery, parseUrl, toSearch } from "./url";
import type { UrlState } from "./url";

const state = (patch: Partial<UrlState>): UrlState => ({ ...EMPTY_URL_STATE, ...patch });

describe("parseUrl", () => {
  it("reads a ticker and a preset, ignoring case", () => {
    expect(parseUrl("?t=spy&range=3y")).toEqual(state({ ticker: "SPY", range: "3Y" }));
    expect(parseUrl("?t=SPY&range=full")).toEqual(state({ ticker: "SPY", range: "FULL" }));
  });

  it("means Full history when only a ticker is given", () => {
    expect(parseUrl("?t=SPY")).toEqual(state({ ticker: "SPY" }));
  });

  it("reads custom dates and lets them win over a preset", () => {
    expect(parseUrl("?t=SPY&start=2023-01-01&end=2026-09-30")).toEqual(
      state({ ticker: "SPY", start: "2023-01-01", end: "2026-09-30" }),
    );
    expect(parseUrl("?t=SPY&range=3Y&start=2023-01-01")).toEqual(state({ ticker: "SPY", start: "2023-01-01" }));
  });

  it("reads the rolling window", () => {
    expect(parseUrl("?t=SPY&win=126").win).toBe(126);
    expect(parseUrl("?t=SPY&win=252").win).toBe(252);
  });

  it("drops invalid values", () => {
    expect(parseUrl("?t=BRK%20B&range=YTD&win=60&start=2023-02-30&end=soon")).toEqual(EMPTY_URL_STATE);
    expect(parseUrl("?t=.HIDDEN")).toEqual(EMPTY_URL_STATE);
    expect(parseUrl("?t=ABCDEFGHIJKLM")).toEqual(EMPTY_URL_STATE);
    expect(parseUrl("?t=&range=1Y")).toEqual(EMPTY_URL_STATE);
  });

  it("accepts the server's ticker characters", () => {
    expect(parseUrl("?t=brk-b").ticker).toBe("BRK-B");
    expect(parseUrl("?t=%5EGSPC").ticker).toBe("^GSPC");
    expect(parseUrl("?t=eurusd%3Dx").ticker).toBe("EURUSD=X");
  });

  it("handles an empty search", () => {
    expect(parseUrl("")).toEqual(EMPTY_URL_STATE);
  });
});

describe("toSearch", () => {
  it("writes the documented shapes", () => {
    expect(toSearch(state({ ticker: "SPY", range: "3Y" }))).toBe("?t=SPY&range=3Y");
    expect(toSearch(state({ ticker: "SPY", start: "2023-01-01", end: "2026-09-30" }))).toBe(
      "?t=SPY&start=2023-01-01&end=2026-09-30",
    );
    expect(toSearch(state({ ticker: "SPY", range: "FULL", win: 126 }))).toBe("?t=SPY&range=FULL&win=126");
  });

  it("is empty for the empty state and omits what is null", () => {
    expect(toSearch(EMPTY_URL_STATE)).toBe("");
    expect(toSearch(state({ ticker: "SPY" }))).toBe("?t=SPY");
  });

  it("writes custom dates instead of a preset when both are set", () => {
    expect(toSearch(state({ ticker: "SPY", range: "3Y", start: "2023-01-01" }))).toBe("?t=SPY&start=2023-01-01");
  });

  it("round-trips every shape", () => {
    const cases: UrlState[] = [
      EMPTY_URL_STATE,
      state({ ticker: "SPY" }),
      state({ ticker: "BRK-B", range: "5Y", win: 252 }),
      state({ ticker: "^GSPC", start: "2023-01-01", end: "2026-09-30", win: 126 }),
      state({ ticker: "SPY", end: "2026-09-30" }),
      state({ range: "3Y" }),
    ];
    for (const s of cases) expect(parseUrl(toSearch(s))).toEqual(s);
  });

  it("cleans a dirty search to the canonical form", () => {
    expect(toSearch(parseUrl("?range=3y&t=spy&junk=1&win=7"))).toBe("?t=SPY&range=3Y");
  });
});

describe("applyPatch", () => {
  const base = state({ ticker: "SPY", range: "3Y", win: 126 });

  it("keeps range and window when the ticker changes", () => {
    expect(applyPatch(base, { ticker: "qqq" })).toEqual(state({ ticker: "QQQ", range: "3Y", win: 126 }));
  });

  it("clears the dates when a preset is chosen, and the preset when dates are entered", () => {
    const dated = state({ ticker: "SPY", start: "2023-01-01", end: "2026-01-01" });
    expect(applyPatch(dated, { range: "5Y" })).toEqual(state({ ticker: "SPY", range: "5Y" }));
    expect(applyPatch(base, { start: "2023-01-01", end: "2026-01-01" })).toEqual(
      state({ ticker: "SPY", start: "2023-01-01", end: "2026-01-01", win: 126 }),
    );
  });
});

describe("checkTicker", () => {
  it("upper-cases a valid ticker and trims it", () => {
    expect(checkTicker("  spy ")).toEqual({ ok: true, ticker: "SPY" });
  });

  it("explains an invalid ticker in a plain sentence, as the server does", () => {
    expect(checkTicker("BRK B")).toEqual({
      ok: false,
      message: "BRK B is not a valid ticker. Use 1 to 12 letters, digits or . ^ = - (for example SPY or BRK-B).",
    });
    expect(checkTicker("").ok).toBe(false);
  });

  it("limits suggestion queries to safe text", () => {
    expect(isSuggestQuery("SP")).toBe(true);
    expect(isSuggestQuery("S P")).toBe(false);
    expect(isSuggestQuery("")).toBe(false);
  });
});
