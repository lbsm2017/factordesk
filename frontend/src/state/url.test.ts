import { describe, expect, it } from "vitest";
import { applyPatch, checkTicker, EMPTY_URL_STATE, isSuggestQuery, parseUrl, toSearch } from "./url";
import type { UrlState } from "./url";

const state = (patch: Partial<UrlState>): UrlState => ({ ...EMPTY_URL_STATE, ...patch });

describe("parseUrl", () => {
  it("reads a ticker and a preset, ignoring case", () => {
    expect(parseUrl("?t=spy&range=3y")).toEqual(state({ ticker: "SPY", range: "3Y" }));
    expect(parseUrl("?t=SPY&range=full")).toEqual(state({ ticker: "SPY", range: "FULL" }));
    expect(parseUrl("?t=SPY&range=10y")).toEqual(state({ ticker: "SPY", range: "10Y" }));
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

  it("reads the statistics switch only as stats=1", () => {
    expect(parseUrl("?t=SPY&stats=1").stats).toBe(true);
    expect(parseUrl("?t=SPY&stats=0").stats).toBe(false);
    expect(parseUrl("?t=SPY&stats=yes").stats).toBe(false);
    expect(parseUrl("?t=SPY").stats).toBe(false);
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
    expect(toSearch(state({ ticker: "ZM", range: "5Y", win: 126, stats: true }))).toBe("?t=ZM&range=5Y&win=126&stats=1");
    expect(toSearch(state({ ticker: "ZM", stats: false }))).toBe("?t=ZM");
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
      state({ ticker: "SPY", range: "10Y" }),
      state({ ticker: "^GSPC", start: "2023-01-01", end: "2026-09-30", win: 126 }),
      state({ ticker: "SPY", end: "2026-09-30" }),
      state({ range: "3Y" }),
      state({ ticker: "SPY", range: "10Y", stats: true }),
      state({ stats: true }),
    ];
    for (const s of cases) expect(parseUrl(toSearch(s))).toEqual(s);
  });

  it("cleans a dirty search to the canonical form", () => {
    expect(toSearch(parseUrl("?range=3y&t=spy&junk=1&win=7"))).toBe("?t=SPY&range=3Y");
    expect(toSearch(parseUrl("?stats=on&t=spy"))).toBe("?t=SPY");
    expect(toSearch(parseUrl("?stats=1&t=spy"))).toBe("?t=SPY&stats=1");
  });
});

describe("applyPatch", () => {
  const base = state({ ticker: "SPY", range: "3Y", win: 126 });

  it("keeps range and window when the ticker changes", () => {
    expect(applyPatch(base, { ticker: "qqq" })).toEqual(state({ ticker: "QQQ", range: "3Y", win: 126 }));
  });

  it("keeps the statistics switch when the ticker or the range changes", () => {
    const on = { ...base, stats: true };
    expect(applyPatch(on, { ticker: "qqq" }).stats).toBe(true);
    expect(applyPatch(on, { range: "10Y" }).stats).toBe(true);
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

describe("mode", () => {
  it("is the ticker mode unless the URL says m=track, so old URLs keep their meaning", () => {
    expect(parseUrl("").mode).toBe("ticker");
    expect(parseUrl("?t=SPY&range=3Y").mode).toBe("ticker");
    expect(parseUrl("?m=track").mode).toBe("track");
    expect(parseUrl("?m=TRACK").mode).toBe("ticker");
    expect(parseUrl("?m=portfolio").mode).toBe("ticker");
  });

  it("writes m=track only for the track-record mode", () => {
    expect(toSearch(state({ mode: "track" }))).toBe("?m=track");
    expect(toSearch(state({ ticker: "SPY", range: "3Y", mode: "track" }))).toBe("?t=SPY&range=3Y&m=track");
    expect(toSearch(state({ ticker: "SPY", range: "3Y" }))).toBe("?t=SPY&range=3Y");
  });

  it("round-trips and patches", () => {
    const text = "?t=SPY&m=track";
    expect(toSearch(parseUrl(text))).toBe(text);
    expect(applyPatch(state({ ticker: "SPY" }), { mode: "track" }).mode).toBe("track");
  });
});
