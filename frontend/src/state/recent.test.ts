import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { addRecent, getRecent, RECENT_KEY, resetRecentCache } from "./recent";

beforeEach(() => {
  window.localStorage.clear();
  resetRecentCache();
});
afterEach(() => vi.restoreAllMocks());

describe("recent tickers", () => {
  it("keeps the newest first, without duplicates", () => {
    addRecent("SPY");
    addRecent("qqq");
    addRecent("SPY");
    expect(getRecent()).toEqual(["SPY", "QQQ"]);
    expect(JSON.parse(window.localStorage.getItem(RECENT_KEY) ?? "[]")).toEqual(["SPY", "QQQ"]);
  });

  it("keeps eight", () => {
    for (let i = 0; i < 12; i++) addRecent(`T${i}`);
    expect(getRecent()).toHaveLength(8);
    expect(getRecent()[0]).toBe("T11");
  });

  it("reads what an earlier visit stored and drops junk", () => {
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(["spy", 7, "BAD TICKER", "SPY", "QQQ"]));
    resetRecentCache();
    expect(getRecent()).toEqual(["SPY", "QQQ"]);
    window.localStorage.setItem(RECENT_KEY, "not json");
    resetRecentCache();
    expect(getRecent()).toEqual([]);
  });

  it("works when storage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    resetRecentCache();
    expect(getRecent()).toEqual([]);
    expect(() => addRecent("SPY")).not.toThrow();
    expect(getRecent()).toEqual(["SPY"]);
  });
});
