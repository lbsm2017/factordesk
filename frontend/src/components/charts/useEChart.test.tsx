import { render, waitFor } from "@testing-library/react";
import { useRef } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { readChartTokens } from "./chartTokens";
import { useEChart } from "./useEChart";

const fake = vi.hoisted(() => {
  const instance = {
    group: "",
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: vi.fn(() => false),
  };
  return {
    instance,
    init: vi.fn(() => instance),
    connect: vi.fn(),
    disconnect: vi.fn(),
  };
});

vi.mock("./echartsCore", () => ({ init: fake.init, connect: fake.connect, disconnect: fake.disconnect }));

function Probe({ option, group }: { option: Record<string, unknown> | null; group?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEChart(ref, option, group ? { group } : {});
  return <div ref={ref} aria-hidden="true" />;
}

describe("useEChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("initialises the SVG renderer lazily, applies the option without animation, and disposes on unmount", async () => {
    const { unmount } = render(<Probe option={{ series: [] }} />);
    await waitFor(() => expect(fake.instance.setOption).toHaveBeenCalled());
    expect(fake.init).toHaveBeenCalledWith(expect.any(HTMLElement), undefined, { renderer: "svg" });
    expect(fake.instance.setOption).toHaveBeenCalledWith({ animation: false, series: [] }, { notMerge: true });
    unmount();
    expect(fake.instance.dispose).toHaveBeenCalledTimes(1);
  });

  it("draws nothing for a null option", async () => {
    render(<Probe option={null} />);
    await waitFor(() => expect(fake.init).toHaveBeenCalled());
    expect(fake.instance.setOption).not.toHaveBeenCalled();
  });

  it("connects charts that share a group and disconnects on unmount", async () => {
    const { unmount } = render(<Probe option={{}} group="rolling" />);
    await waitFor(() => expect(fake.connect).toHaveBeenCalledWith("rolling"));
    expect(fake.instance.group).toBe("rolling");
    unmount();
    expect(fake.disconnect).toHaveBeenCalledWith("rolling");
  });
});

describe("readChartTokens", () => {
  it("reads colours from the CSS custom properties", () => {
    const root = document.documentElement;
    root.style.setProperty("--ink", "rgb(1, 2, 3)");
    root.style.setProperty("--f3", "rgb(4, 5, 6)");
    try {
      const tokens = readChartTokens(root);
      expect(tokens.ink).toBe("rgb(1, 2, 3)");
      expect(tokens.factors[2]).toBe("rgb(4, 5, 6)");
      expect(tokens.factors).toHaveLength(5);
    } finally {
      root.style.removeProperty("--ink");
      root.style.removeProperty("--f3");
    }
  });

  it("falls back to currentColor when a token is missing", () => {
    expect(readChartTokens(document.documentElement).axis).toBe("currentColor");
  });
});
