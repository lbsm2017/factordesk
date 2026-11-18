import { dateLong, dateShort, num, pct } from "../../format";
import { EmptyState } from "./EmptyState";
import { fin } from "./leadHelpers";
import type { ReportPanelProps } from "./types";
import "./lead.css";

interface Cell {
  label: string;
  value: string;
  note: string;
  cls: string;
}

/** Five cells split by hairlines, one plain line each (design 3). Empty state when the regression is not ok. */
export function KpiStrip({ report }: ReportPanelProps) {
  const g = report.regression;
  const d = report.data;
  if (g.status !== "ok") {
    return (
      <section className="kpis" id="kpis" aria-label="Headline statistics">
        <EmptyState
          reason={g.reason ?? "The regression could not be computed."}
          action="Widen the date range and run the report again."
        />
      </section>
    );
  }
  const alpha = fin(g.alpha_annual);
  const r2 = fin(g.r2);
  const sigma = fin(g.sigma_e_annual);
  let alphaNote = "Significance not available";
  let alphaCls = "ns";
  if (g.alpha_tag === "reliable") {
    alphaNote = "Distinguishable from zero at 5%";
    alphaCls = "";
  } else if (g.alpha_tag === "noise") {
    alphaNote = "Not distinguishable from zero";
  }
  const cells: Cell[] = [
    { label: "Alpha, a year", value: alpha === null ? "n/a" : pct(alpha), note: alphaNote, cls: alphaCls },
    {
      label: "R²",
      value: r2 === null ? "n/a" : num(r2, 4),
      note: "Share of daily variance the factors explain",
      cls: "",
    },
    {
      label: "Residual volatility",
      value: sigma === null ? "n/a" : pct(sigma, 1, false),
      note: "A year, left unexplained by the factors",
      cls: "",
    },
    {
      label: "Observations",
      value: d.n_obs.toLocaleString("en-US"),
      note: d.n_excluded ? `Trading days; ${d.n_excluded} excluded` : "Trading days; none excluded",
      cls: "",
    },
    {
      label: "Analysed range",
      value: `${dateShort(d.actual_start)} to ${dateShort(d.actual_end)}`,
      note: `Requested ${dateLong(d.requested_start)} to ${dateLong(d.requested_end)}`,
      cls: "dates",
    },
  ];
  return (
    <section className="kpis" id="kpis" aria-label="Headline statistics">
      <dl>
        {cells.map((c) => (
          <div key={c.label} className={`kpi ${c.cls}`.trim()}>
            <dt>{c.label}</dt>
            <dd className="v">{c.value}</dd>
            <dd className="n">{c.note}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
