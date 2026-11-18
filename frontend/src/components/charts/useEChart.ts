import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import type { ECharts, EChartsCoreOption } from "./echartsCore";

export interface UseEChartOptions {
  /** Charts with the same group id are connected through `echarts.connect` (zoom and hover move together). */
  group?: string;
}

/**
 * Mount an ECharts instance (SVG renderer, no animation) into `containerRef` and keep it in sync
 * with `option`. ECharts loads lazily. The instance is disposed on unmount and resized with its
 * container. The container should be `aria-hidden`: the table beside the chart carries the numbers.
 * Pass `null` to draw nothing yet. Tooltip formatters in `option` must escape every string.
 */
export function useEChart(
  containerRef: RefObject<HTMLElement | null>,
  option: EChartsCoreOption | null,
  { group }: UseEChartOptions = {},
): ECharts | null {
  const [chart, setChart] = useState<ECharts | null>(null);
  const instanceRef = useRef<ECharts | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let cancelled = false;
    let observer: ResizeObserver | null = null;
    let leave: (() => void) | null = null;
    void import("./echartsCore").then((core) => {
      if (cancelled) return;
      const instance = core.init(el, undefined, { renderer: "svg" });
      if (group) {
        instance.group = group;
        core.connect(group);
        leave = () => core.disconnect(group);
      }
      if (typeof ResizeObserver !== "undefined") {
        observer = new ResizeObserver(() => instance.resize());
        observer.observe(el);
      }
      instanceRef.current = instance;
      setChart(instance);
    });
    return () => {
      cancelled = true;
      observer?.disconnect();
      leave?.();
      const instance = instanceRef.current;
      instanceRef.current = null;
      if (instance && !instance.isDisposed()) instance.dispose();
      setChart(null);
    };
  }, [containerRef, group]);

  useEffect(() => {
    if (!chart || chart.isDisposed() || !option) return;
    chart.setOption({ animation: false, ...option }, { notMerge: true });
  }, [chart, option]);

  return chart;
}
