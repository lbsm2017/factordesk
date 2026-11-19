import { useEffect, useMemo, useRef, useState } from "react";
import { useChartTokens } from "../charts/chartTokens";
import { useEChart } from "../charts/useEChart";
import { isSubjectReport } from "../../report/subject";
import { priceOutcome } from "../../text/outcome";
import { Panel } from "./Panel";
import { priceModel, priceOption, visibleLabels } from "./priceModel";
import type { PriceModel } from "./priceModel";
import type { ReportPanelProps } from "./types";
import "./PricePanel.css";

const QUESTION = "How has the price moved over the window? Shaded days are not in the analysis.";
const RECORD_QUESTION = "How has the record grown over the window? Shaded months are not in the analysis.";

interface DataZoomState {
  startValue?: unknown;
  endValue?: unknown;
}

interface View {
  model: PriceModel;
  full: boolean;
  start: number;
  end: number;
}

interface PriceChartProps {
  model: PriceModel;
  /** Show the whole history instead of the loaded window. */
  full: boolean;
}

/** The ECharts plot and the two "Not analysed" labels above it. Mounted only when there is a line to draw. */
function PriceChart({ model, full }: PriceChartProps) {
  const ref = useRef<HTMLDivElement>(null);
  const tokens = useChartTokens();
  const option = useMemo(() => priceOption(model, tokens, { full }), [model, tokens, full]);
  const chart = useEChart(ref, option);
  const [view, setView] = useState<View | null>(null);

  // Wheel and pinch zoom move the window; the labels follow what is on screen.
  useEffect(() => {
    if (!chart) return;
    const onZoom = () => {
      const zoom = (chart.getOption() as { dataZoom?: DataZoomState[] }).dataZoom?.[0];
      const start = Number(zoom?.startValue);
      const end = Number(zoom?.endValue);
      if (Number.isFinite(start) && Number.isFinite(end)) setView({ model, full, start, end });
    };
    chart.on("datazoom", onZoom);
    return () => {
      if (!chart.isDisposed()) chart.off("datazoom", onZoom);
    };
  }, [chart, model, full]);

  const first = model.points[0];
  const last = model.points[model.points.length - 1];
  const loaded = { start: full ? (first?.ms ?? 0) : model.initialStartMs, end: last?.ms ?? 0 };
  const range = view && view.model === model && view.full === full ? view : loaded;
  const labels = visibleLabels(model, range);

  return (
    <div className="price-main">
      <div className="price-zones">
        <span className="zone-tag">{labels.start}</span>
        <span className="zone-tag zone-tag-end">{labels.end}</span>
      </div>
      <div ref={ref} className="price-chart" aria-hidden="true" />
    </div>
  );
}

/** Panel 4 (design D4): price over time. The chart is decoration; the table beside it carries the numbers. */
export function PricePanel({ report }: ReportPanelProps) {
  const model = useMemo(() => priceModel(report), [report]);
  // The user's choice belongs to one report: a new report starts on the analysed window again.
  const [fullFor, setFullFor] = useState<PriceModel | null>(null);

  if (!model) {
    return (
      <Panel
        id="price"
        title="Price"
        question={QUESTION}
        empty={{
          reason: "Insufficient data: fewer than two price points were returned for this ticker and window.",
          action: "Check the ticker symbol or choose a later start date.",
        }}
      />
    );
  }

  const full = fullFor === model;
  const record = isSubjectReport(report);
  const toggle = model.canShowFull ? (
    <button type="button" className="zoom-toggle" onClick={() => setFullFor(full ? null : model)}>
      {full ? "Show analysed range" : "Show full history"}
    </button>
  ) : undefined;

  return (
    <Panel
      id="price"
      title={record ? "Growth of 100" : "Price"}
      question={record ? RECORD_QUESTION : QUESTION}
      outcome={priceOutcome(report)}
      legend={toggle}
      footnote={
        record
          ? "Built from the uploaded monthly returns, for context only; no statistic uses this line."
          : `Adjusted close from ${report.data.price_source}, for context only; no statistic uses the price line.`
      }
    >
      <div className="price-wrap">
        <PriceChart model={model} full={full} />
        <table className="side">
          <caption className="vh">{record ? "Data points" : "Price points"}</caption>
          <thead className="vh">
            <tr>
              <th scope="col">Point</th>
              <th scope="col">{record ? "Level" : "Adjusted close"}</th>
            </tr>
          </thead>
          <tbody>
            {model.rows.map((r) => (
              <tr key={r.label} className={r.muted ? "muted-row" : undefined}>
                <th scope="row">
                  {r.label}
                  <span className="sub">{r.sub}</span>
                </th>
                <td className="num">{r.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
