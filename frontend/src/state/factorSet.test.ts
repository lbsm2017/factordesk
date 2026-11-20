import { describe, expect, it } from "vitest";
import { DEFAULT_FACTOR_SET, factorSetParam, parseFactorSet } from "./factorSet";
import { applyPatch, EMPTY_URL_STATE, parseUrl, toSearch } from "./url";

describe("factor set in the URL", () => {
  it("reads fs=europe, ignoring case, and treats anything else as the US set", () => {
    expect(parseUrl("?t=SPY&fs=europe").fs).toBe("europe");
    expect(parseUrl("?t=SPY&fs=EUROPE").fs).toBe("europe");
    expect(parseUrl("?t=SPY&fs=us").fs).toBe("us");
    expect(parseUrl("?t=SPY&fs=asia").fs).toBe("us");
    expect(parseUrl("?t=SPY").fs).toBe("us");
    expect(parseFactorSet(null)).toBe(DEFAULT_FACTOR_SET);
  });

  it("writes fs=europe and never writes the US set", () => {
    expect(toSearch({ ...EMPTY_URL_STATE, ticker: "SPY", fs: "europe" })).toBe("?t=SPY&fs=europe");
    expect(toSearch({ ...EMPTY_URL_STATE, ticker: "SPY", fs: "us" })).toBe("?t=SPY");
    expect(toSearch({ ...EMPTY_URL_STATE, ticker: "SPY", ccy: "EUR", fs: "europe" })).toBe("?t=SPY&ccy=EUR&fs=europe");
  });

  it("round trips through parse and serialise, and a patch changes only the set", () => {
    const search = "?t=SPY&range=3Y&ccy=EUR&fs=europe";
    expect(toSearch(parseUrl(search))).toBe(search);
    // An explicit fs=us is cleaned out of the URL.
    expect(toSearch(parseUrl("?t=SPY&fs=us"))).toBe("?t=SPY");
    const next = applyPatch(parseUrl("?t=SPY&range=3Y"), { fs: "europe" });
    expect(toSearch(next)).toBe("?t=SPY&range=3Y&fs=europe");
    expect(toSearch(applyPatch(next, { fs: "us" }))).toBe("?t=SPY&range=3Y");
  });

  it("sends factor_set only for the Europe set", () => {
    expect(factorSetParam("europe")).toEqual({ factor_set: "europe" });
    expect(factorSetParam("us")).toEqual({});
  });
});
