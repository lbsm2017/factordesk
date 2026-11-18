import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import type * as EChartsCore from "./echartsCore";
import type { ECharts, EChartsCoreOption } from "./echartsCore";

export interface UseEChartOptions {
  /** Charts with the same group id are connected through `echarts.connect` (zoom and hover move together). */
  group?: string;
}

type Core = typeof EChartsCore;

/** How many mounted charts use each group, so one unmount does not unlink the others. */
const groupUsers = new Map<string, number>();

function joinGroup(core: Core, group: string): () => void {
  groupUsers.set(group, (groupUsers.get(group) ?? 0) + 1);
  core.connect(group);
  let left = false;
  return () => {
    if (left) return;
    left = true;
    const remaining = (groupUsers.get(group) ?? 1) - 1;
    if (remaining > 0) {
      groupUsers.set(group, remaining);
    } else {
      groupUsers.delete(group);
      core.disconnect(group);
    }
  };
}

/**
 * Mount an ECharts instance (SVG renderer, no animation) into `containerRef` and keep it in sync
 * with `option`. ECharts loads lazily. The instance is disposed on unmount and resized with its
 * container. The container should be `aria-hidden`: the table beside the chart carries the numbers.
 * Pass `null` to draw nothing yet. Tooltip formatters in `option` must escape every string.
 *
 * Rules the hook relies on:
 * - The container element must be mounted together with the component that calls the hook (render
 *   the chart in its own child component), because the instance is created once per mount.
 * - If ECharts fails to load or to draw, the chart stays blank and the page keeps working: the
 *   tables beside it carry every number. The failure is logged to the console only.
 * - Connected charts are linked until the last chart of the group unmounts.
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
    import("./echartsCore")
      .then((core) => {
        if (cancelled) return;
        const instance = core.init(el, undefined, { renderer: "svg" });
        instanceRef.current = instance;
        if (group) {
          instance.group = group;
          leave = joinGroup(core, group);
        }
        if (typeof ResizeObserver !== "undefined") {
          observer = new ResizeObserver(() => {
            if (!instance.isDisposed()) instance.resize();
          });
          observer.observe(el);
        }
        setChart(instance);
      })
      .catch((error: unknown) => {
        console.warn("factordesk: the chart could not be drawn; the tables carry the numbers.", error);
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
    try {
      chart.setOption({ animation: false, ...option }, { notMerge: true });
    } catch (error: unknown) {
      console.warn("factordesk: the chart option was rejected; the tables carry the numbers.", error);
    }
  }, [chart, option]);

  return chart;
}
