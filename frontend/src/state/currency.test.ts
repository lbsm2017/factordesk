import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CURRENCY_KEY, parseCurrency, readStoredCurrency, resolveCurrency, useCurrency } from "./currency";
import { EMPTY_URL_STATE, parseUrl, toSearch } from "./url";

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("parseCurrency", () => {
  it("accepts USD and EUR in any case and rejects everything else", () => {
    expect(parseCurrency("EUR")).toBe("EUR");
    expect(parseCurrency("eur")).toBe("EUR");
    expect(parseCurrency(" usd ")).toBe("USD");
    expect(parseCurrency("GBP")).toBeNull();
    expect(parseCurrency("")).toBeNull();
    expect(parseCurrency(null)).toBeNull();
    expect(parseCurrency(undefined)).toBeNull();
  });
});

describe("ccy in the URL", () => {
  it("reads ccy=EUR and ccy=USD, and drops other values", () => {
    expect(parseUrl("?t=SPY&ccy=EUR").ccy).toBe("EUR");
    expect(parseUrl("?t=SPY&ccy=eur").ccy).toBe("EUR");
    expect(parseUrl("?t=SPY&ccy=USD").ccy).toBe("USD");
    expect(parseUrl("?t=SPY&ccy=CHF").ccy).toBeNull();
    expect(parseUrl("?t=SPY").ccy).toBeNull();
  });

  it("writes ccy only when the state names a currency", () => {
    expect(toSearch({ ...EMPTY_URL_STATE, ticker: "SPY", ccy: "EUR" })).toBe("?t=SPY&ccy=EUR");
    expect(toSearch({ ...EMPTY_URL_STATE, ticker: "SPY", ccy: null })).toBe("?t=SPY");
  });
});

describe("resolveCurrency", () => {
  it("lets the URL win over the stored choice, which wins over the default", () => {
    expect(resolveCurrency("EUR", "USD")).toBe("EUR");
    expect(resolveCurrency("USD", "EUR")).toBe("USD");
    expect(resolveCurrency(null, "EUR")).toBe("EUR");
    expect(resolveCurrency(null, null)).toBe("USD");
  });
});

describe("storage", () => {
  it("reads the stored choice and ignores junk", () => {
    window.localStorage.setItem(CURRENCY_KEY, "EUR");
    expect(readStoredCurrency()).toBe("EUR");
    window.localStorage.setItem(CURRENCY_KEY, "gold");
    expect(readStoredCurrency()).toBeNull();
  });

  it("is safe when reading throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(readStoredCurrency()).toBeNull();
    const { result } = renderHook(() => useCurrency(null, vi.fn()));
    expect(result.current[0]).toBe("USD");
  });
});

describe("useCurrency", () => {
  it("starts from the stored choice when the URL says nothing", () => {
    window.localStorage.setItem(CURRENCY_KEY, "EUR");
    const { result } = renderHook(() => useCurrency(null, vi.fn()));
    expect(result.current[0]).toBe("EUR");
  });

  it("lets ccy in the URL override the stored choice", () => {
    window.localStorage.setItem(CURRENCY_KEY, "EUR");
    const { result } = renderHook(() => useCurrency("USD", vi.fn()));
    expect(result.current[0]).toBe("USD");
    const other = renderHook(() => useCurrency("EUR", vi.fn()));
    expect(other.result.current[0]).toBe("EUR");
  });

  it("stores the choice and writes only EUR to the URL", () => {
    const commit = vi.fn();
    const { result } = renderHook(() => useCurrency(null, commit));
    act(() => result.current[1]("EUR"));
    expect(window.localStorage.getItem(CURRENCY_KEY)).toBe("EUR");
    expect(commit).toHaveBeenLastCalledWith({ ccy: "EUR" });
    expect(result.current[0]).toBe("EUR");
    act(() => result.current[1]("USD"));
    expect(window.localStorage.getItem(CURRENCY_KEY)).toBe("USD");
    expect(commit).toHaveBeenLastCalledWith({ ccy: null });
    expect(result.current[0]).toBe("USD");
  });

  it("still works for the page view when writing to storage throws", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    const commit = vi.fn();
    const { result } = renderHook(() => useCurrency(null, commit));
    act(() => result.current[1]("EUR"));
    expect(result.current[0]).toBe("EUR");
    expect(commit).toHaveBeenCalledWith({ ccy: "EUR" });
  });
});
