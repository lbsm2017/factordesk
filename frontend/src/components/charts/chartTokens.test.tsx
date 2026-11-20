import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useChartTokens } from "./chartTokens";

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("style");
});

describe("useChartTokens", () => {
  it("reads the token values again when data-theme changes", async () => {
    document.documentElement.style.setProperty("--ink", "#111111");
    const { result } = renderHook(() => useChartTokens());
    expect(result.current.ink).toBe("#111111");
    await act(async () => {
      document.documentElement.style.setProperty("--ink", "#eeeeee");
      document.documentElement.setAttribute("data-theme", "dark");
      await Promise.resolve();
    });
    expect(result.current.ink).toBe("#eeeeee");
  });

  it("keeps the same object when nothing changed", async () => {
    const { result } = renderHook(() => useChartTokens());
    const before = result.current;
    await act(async () => {
      document.documentElement.setAttribute("data-theme", "light");
      await Promise.resolve();
    });
    expect(result.current).toBe(before);
  });
});
