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

  it("means 10Y and FF6 when only a ticker is given", () => {
    expect(parseUrl("?t=SPY")).toEqual(state({ ticker: "SPY" }));
    expect(parseUrl("?t=SPY")).toMatchObject({ range: "10Y", model: "ff6" });
  });

  it("reads custom dates and lets them win over a preset", () => {
    expect(parseUrl("?t=SPY&start=2023-01-01&end=2026-09-30")).toEqual(
      state({ ticker: "SPY", range: null, start: "2023-01-01", end: "2026-09-30" }),
    );
    expect(parseUrl("?t=SPY&range=3Y&start=2023-01-01")).toEqual(state({ ticker: "SPY", range: null, start: "2023-01-01" }));
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
    expect(toSearch(state({ ticker: "SPY", range: null, start: "2023-01-01", end: "2026-09-30" }))).toBe(
      "?t=SPY&start=2023-01-01&end=2026-09-30",
    );
    expect(toSearch(state({ ticker: "SPY", range: "FULL", win: 126 }))).toBe("?t=SPY&range=FULL&win=126");
    expect(toSearch(state({ ticker: "ZM", range: "5Y", win: 126, stats: true }))).toBe("?t=ZM&range=5Y&win=126&stats=1");
    expect(toSearch(state({ ticker: "ZM", stats: false }))).toBe("?t=ZM");
  });

  it("never writes the default range, and writes Full history as range=FULL", () => {
    expect(toSearch(state({ ticker: "SPY", range: "10Y" }))).toBe("?t=SPY");
    expect(toSearch(state({ ticker: "SPY", range: "FULL" }))).toBe("?t=SPY&range=FULL");
    expect(toSearch(state({ ticker: "SPY", range: "5Y" }))).toBe("?t=SPY&range=5Y");
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
      state({ ticker: "SPY", range: "FULL" }),
      state({ ticker: "SPY", range: "FULL", model: "ff5" }),
      state({ ticker: "SPY", model: "ff5" }),
      state({ ticker: "^GSPC", range: null, start: "2023-01-01", end: "2026-09-30", win: 126 }),
      state({ ticker: "SPY", range: null, end: "2026-09-30" }),
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
    const dated = state({ ticker: "SPY", range: null, start: "2023-01-01", end: "2026-01-01" });
    expect(applyPatch(dated, { range: "5Y" })).toEqual(state({ ticker: "SPY", range: "5Y" }));
    expect(applyPatch(base, { start: "2023-01-01", end: "2026-01-01" })).toEqual(
      state({ ticker: "SPY", range: null, start: "2023-01-01", end: "2026-01-01", win: 126 }),
    );
  });

  it("goes back to the default range when the custom dates are cleared", () => {
    const dated = state({ ticker: "SPY", range: null, start: "2023-01-01", end: "2026-01-01" });
    expect(applyPatch(dated, { start: null, end: null }).range).toBe("10Y");
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
  it("is the ticker mode unless the URL says m=track or m=portfolio, so old URLs keep their meaning", () => {
    expect(parseUrl("").mode).toBe("ticker");
    expect(parseUrl("?t=SPY&range=3Y").mode).toBe("ticker");
    expect(parseUrl("?m=track").mode).toBe("track");
    expect(parseUrl("?m=TRACK").mode).toBe("ticker");
    expect(parseUrl("?m=portfolio").mode).toBe("portfolio");
    expect(parseUrl("?m=Portfolio").mode).toBe("ticker");
    expect(parseUrl("?m=nonsense").mode).toBe("ticker");
  });

  it("writes m=portfolio for the portfolio mode and nothing for the ticker mode", () => {
    expect(toSearch(state({ mode: "portfolio" }))).toBe("?m=portfolio");
    expect(toSearch(state({ mode: "portfolio", model: "ff5" }))).toBe("?m=portfolio&model=ff5");
    expect(toSearch(parseUrl("?m=portfolio"))).toBe("?m=portfolio");
    expect(applyPatch(state({}), { mode: "portfolio" }).mode).toBe("portfolio");
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

describe("model", () => {
  it("is FF6 unless the URL says otherwise, and an explicit model keeps its meaning", () => {
    expect(EMPTY_URL_STATE.model).toBe("ff6");
    expect(parseUrl("").model).toBe("ff6");
    expect(parseUrl("?t=SPY&range=3Y").model).toBe("ff6");
    expect(parseUrl("?t=SPY&model=ff6").model).toBe("ff6");
    expect(parseUrl("?t=SPY&model=FF6").model).toBe("ff6");
    expect(parseUrl("?t=SPY&model=ff5").model).toBe("ff5");
    expect(parseUrl("?t=SPY&model=FF5").model).toBe("ff5");
    expect(parseUrl("?t=SPY&model=ff7").model).toBe("ff6");
  });

  it("writes model=ff5 for FF5 and nothing for FF6", () => {
    expect(toSearch(state({ ticker: "SPY", range: "3Y", model: "ff5" }))).toBe("?t=SPY&range=3Y&model=ff5");
    expect(toSearch(state({ ticker: "SPY", range: "3Y", model: "ff6" }))).toBe("?t=SPY&range=3Y");
    expect(toSearch(state({ mode: "track", model: "ff5" }))).toBe("?m=track&model=ff5");
    expect(toSearch(state({ mode: "track" }))).toBe("?m=track");
  });

  it("round-trips model=ff5 and patches the model", () => {
    for (const text of ["?t=SPY&model=ff5", "?t=SPY&range=FULL&model=ff5", "?t=SPY&start=2023-01-02&end=2024-01-02&win=126&stats=1&model=ff5", "?t=SPY", "?m=track&model=ff5"]) {
      expect(toSearch(parseUrl(text))).toBe(text);
    }
    const ff5 = applyPatch(state({ ticker: "SPY", range: "5Y" }), { model: "ff5" });
    expect(ff5).toEqual(state({ ticker: "SPY", range: "5Y", model: "ff5" }));
    expect(applyPatch(ff5, { range: "3Y" }).model).toBe("ff5");
  });

  it("keeps an old URL with explicit params, and cleans it to the canonical form", () => {
    const old = parseUrl("?t=spy&range=full&model=ff5&win=126&stats=1&junk=1");
    expect(old).toEqual(state({ ticker: "SPY", range: "FULL", model: "ff5", win: 126, stats: true }));
    expect(toSearch(old)).toBe("?t=SPY&range=FULL&win=126&stats=1&model=ff5");
    expect(toSearch(parseUrl("?t=SPY&range=10Y&model=ff6"))).toBe("?t=SPY");
  });
});
