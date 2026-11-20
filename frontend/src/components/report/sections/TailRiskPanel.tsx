import { Fragment, useId, useState } from "react";
import type { TailRiskSection } from "../../../api/types";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import {
  APPROXIMATE,
  bandName,
  basedOn,
  CAPTION,
  digitsFor,
  HORIZONS,
  horizonInfo,
  INDICATIVE,
  loss,
  METHODS,
  place,
  rowsOf,
  scaleOf,
  scaleText,
  whatItMeans,
} from "./tailRiskModel";
import type { Horizon, Scale, TailFigure, TailHorizon, TailRow } from "./tailRiskModel";
import "./TailRiskPanel.css";

export const TITLE = "Tail risk";

const HOW = [
  "Value at risk (VaR) is the loss that is exceeded on only a small share of periods: 1 in 100 at the 99% level, 1 in 20 at the 95% level. CVaR, also called expected shortfall, is the average loss on the periods beyond the 97.5% (or 95%) level. Losses are computed from simple returns and shown as positive percentages.",
  "Daily figures use the daily returns. Monthly and quarterly figures use returns compounded over whole calendar months or quarters of the same days, never overlapping, with incomplete periods left out. Nothing is scaled up from daily by the square root of time.",
  "Historical uses the observed returns directly and shows n/a when the sample holds too few tail observations. Gaussian uses the average and the standard deviation of the returns. Cornish-Fisher adjusts the Gaussian figure for skew and fat tails, and shows n/a where its formula is not valid. Where Cornish-Fisher VaR is n/a, its CVaR is n/a too. A figure is marked indicative when its formula passes the check only on the range it uses, or when it differs from the historical figure by more than half of it. It is shown, but it should not be read as precise.",
  "Each band is a 90% bootstrap band: the returns are resampled 1,000 times (in blocks for daily returns), and the band holds the middle 90% of the resulting figures. Bands for Gaussian and for historical VaR matched their coverage on simulated data; the others are marked approximate in the tooltip because they tend to be narrow.",
].join(" ");

/** "far from historical (10.2% vs 5.0%)" as a sentence. */
function sentence(text: string): string {
  return text.length === 0 ? text : text.charAt(0).toUpperCase() + text.slice(1);
}

interface LineProps {
  label: string;
  figure: TailFigure | undefined;
  scale: Scale;
  digits: number;
  bandLevel: number;
}

function Line({ label, figure, scale, digits, bandLevel }: LineProps) {
  if (figure === undefined) return null;
  if (figure.value === null) {
    return (
      <li className="tr-line">
        <div className="tr-main">
          <span className="tr-badge">{label}</span>
          <span className="tr-v na">n/a</span>
          <div className="tr-wh na" role="img" aria-label="No figure" />
          <span className="tr-r">no band</span>
        </div>
        <div className="tr-note">
          <span className="tr-why">{sentence(figure.reason ?? "Not available.")}</span>
        </div>
      </li>
    );
  }
  const value = figure.value;
  const band = figure.band;
  const approximate = band !== null && figure.band_quality === "approximate";
  const tail =
    figure.tail_count === null
      ? undefined
      : `${figure.tail_count} observations in the tail; ${figure.expected_tail_obs.toFixed(1)} expected`;
  const range = band ? `${loss(band.low, digits)} to ${loss(band.high, digits)}` : null;
  const name = band
    ? `Estimate ${loss(value, digits)}, ${bandName(bandLevel)} band ${range}`
    : `Estimate ${loss(value, digits)}, no band`;
  return (
    <li className="tr-line">
      <div className="tr-main">
        <span className="tr-badge">{label}</span>
        <span className="tr-v" title={tail}>
          {loss(value, digits)}
        </span>
        <div className={figure.indicative ? "tr-wh ind" : "tr-wh"} role="img" aria-label={name}>
          {band ? (
            <i
              className="tr-band"
              style={{ left: `${place(band.low, scale)}%`, width: `${place(band.high, scale) - place(band.low, scale)}%` }}
            />
          ) : null}
          <i className="tr-dot" style={{ left: `${place(value, scale)}%` }} />
        </div>
        <span className="tr-r" title={approximate ? APPROXIMATE : undefined}>
          {range ?? "no band"}
        </span>
      </div>
      {figure.indicative || (band === null && figure.band_reason) ? (
        <div className="tr-note">
          {figure.indicative ? (
            <span className="tr-flag">
              <svg className="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
                <path d="M10 2.8 18 16.8H2z" />
                <path d="M10 8v4M10 14.4v.3" />
              </svg>
              {INDICATIVE}
            </span>
          ) : null}
          <span className="tr-why">{sentence((figure.indicative ? figure.reason : figure.band_reason) ?? "")}</span>
        </div>
      ) : null}
    </li>
  );
}

function Group({ row, horizon, scale, bandLevel }: { row: TailRow; horizon: Horizon; scale: Scale; bandLevel: number }) {
  const digits = digitsFor(scale);
  return (
    <div className="tr-group" role="group" aria-label={row.label}>
      <div className="tr-head">
        <h3>{row.label}</h3>
        <span className="tr-what">{whatItMeans(row.measure, row.level, horizon)}</span>
        <span className="tr-scale">{scaleText(scale)}</span>
      </div>
      <ul>
        {METHODS.map((m) => (
          <Line key={m.key} label={m.label} figure={row.cells[m.key]} scale={scale} digits={digits} bandLevel={bandLevel} />
        ))}
      </ul>
    </div>
  );
}

function Lines({ horizon }: { horizon: TailHorizon }) {
  const figures = horizon.figures ?? [];
  const bandLevel = horizon.series?.band_level ?? 0.9;
  const rows = rowsOf(figures);
  const scales = {
    var: scaleOf(figures.filter((f) => f.measure === "var")),
    cvar: scaleOf(figures.filter((f) => f.measure === "cvar")),
  };
  return (
    <div className="tr-lines">
      {rows.map((row) => (
        <Group key={row.key} row={row} horizon={horizon.horizon} scale={scales[row.measure]} bandLevel={bandLevel} />
      ))}
      <ul className="tr-legend" aria-label="How to read the lines">
        <li>
          <span className="tr-lg-dot" />
          Estimate
        </li>
        <li>
          <span className="tr-lg-band" />
          {bandName(bandLevel)} band from resampling
        </li>
        <li>
          <span className="tr-lg-dot ind" />
          Indicative: use with care
        </li>
      </ul>
    </div>
  );
}

function HorizonSwitch({
  horizons,
  active,
  onSelect,
}: {
  horizons: readonly TailHorizon[];
  active: Horizon;
  onSelect: (h: Horizon) => void;
}) {
  const uid = useId();
  const labelId = `${uid}-lab`;
  return (
    <div className="seg">
      <span className="seg-lab" id={labelId}>
        Horizon
      </span>
      <div className="seg-btns" role="radiogroup" aria-labelledby={labelId}>
        {horizons.map((h) => {
          const id = `${uid}-${h.horizon}`;
          return (
            <Fragment key={h.horizon}>
              <input
                type="radio"
                name={`${uid}-horizon`}
                id={id}
                value={h.horizon}
                checked={h.horizon === active}
                onChange={() => onSelect(h.horizon)}
              />
              <label htmlFor={id}>{horizonInfo(h.horizon).label}</label>
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}

/** The horizons of a section, in switch order; a report without `by_horizon` has only its own. */
function horizonsOf(s: TailRiskSection): TailHorizon[] {
  const listed = s.by_horizon;
  if (listed != null && listed.length > 0) {
    return HORIZONS.map((h) => listed.find((x) => x.horizon === h.key)).filter((x): x is TailHorizon => x !== undefined);
  }
  if (s.frequency == null) return [];
  return [{ horizon: s.frequency, status: "ok", reason: null, series: s.series, figures: s.figures }];
}

function Ok({ section }: { section: TailRiskSection }) {
  const horizons = horizonsOf(section);
  const own: Horizon = section.frequency ?? "daily";
  const [chosen, setChosen] = useState<Horizon | null>(null);
  const active: Horizon = horizons.some((h) => h.horizon === chosen) ? (chosen as Horizon) : own;
  const current = horizons.find((h) => h.horizon === active) ?? horizons[0];
  if (current === undefined) return null;
  const n = current.series?.n_obs;
  return (
    <Panel
      id="tail-risk"
      title={TITLE}
      question={horizonInfo(current.horizon).question}
      aside={current.status === "ok" && n !== undefined ? `Based on ${basedOn(n, current.horizon)}` : undefined}
      legend={horizons.length > 1 ? <HorizonSwitch horizons={horizons} active={current.horizon} onSelect={setChosen} /> : undefined}
      footnote={CAPTION}
      how={HOW}
    >
      {current.status === "ok" ? (
        <Lines horizon={current} />
      ) : (
        <p className="tr-gap">{current.reason ?? "This horizon could not be computed."}</p>
      )}
    </Panel>
  );
}

/**
 * Panel of the `tail_risk` section (VaR and CVaR; backend `report/sections/tail_risk.py`, spec E7).
 * Registered in `panelRegistry.ts` at position 460, right after Drawdown. Renders nothing when the
 * section is absent (null). One line per method and level, with a Daily | Monthly | Quarterly switch
 * (monthly records have no daily horizon); the switch starts on the series' own frequency.
 */
export function TailRiskPanel({ report }: ReportPanelProps) {
  const s = report.tail_risk;
  if (s == null) return null;
  if (s.status !== "ok") {
    return (
      <Panel
        id="tail-risk"
        title={TITLE}
        empty={{
          reason: s.reason ?? "Tail risk could not be computed for this range.",
          action: "The rest of the report is not affected.",
        }}
      />
    );
  }
  return <Ok section={s} />;
}
