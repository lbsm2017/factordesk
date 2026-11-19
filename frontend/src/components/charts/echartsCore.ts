/**
 * ECharts, tree-shaken from `echarts/core` with the SVG renderer. Only `useEChart` imports this
 * module, and it does so dynamically, so ECharts lands in a lazy chunk and the page frame paints first.
 * Add a chart type or component here when a panel needs it.
 */
import { LineChart } from "echarts/charts";
import {
  DataZoomInsideComponent,
  GridComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import { connect, disconnect, init, use as register } from "echarts/core";
import { SVGRenderer } from "echarts/renderers";

register([
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomInsideComponent,
  MarkAreaComponent,
  MarkLineComponent,
  SVGRenderer,
]);

export { connect, disconnect, init };
export type { EChartsCoreOption, ECharts } from "echarts/core";
