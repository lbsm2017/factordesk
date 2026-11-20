import { Fragment, useId, useState } from "react";
import type { CSSProperties, KeyboardEvent } from "react";
import type { TailRiskSection } from "../../../api/types";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import {
  APPROXIMATE,
  bandName,
  basedOn,
  CAPTION,
  digitsFor,
  GAUSSIAN,
  GAUSSIAN_NOTE,
  groupsOf,
  HORIZONS,
  horizonInfo,
  INDICATIVE,
  levelName,
  loss,
  METHODS,
  oneIn,
  place,
  scaleOf,
  shownFigures,
  tickText,
  ticksOf,
  whatItMeans,
} from "./tailRiskModel";
import type { Horizon, Scale, TailBar, TailFigure, TailGroup, TailHorizon, TailLevel, TailMethod } from "./tailRiskModel";
import "./TailRiskPanel.css";

export const TITLE = "Tail risk";

const HOW = [
  "Value at risk (VaR) is the loss that is exceeded on only a small share of periods: 1 in 100 at the 99% level, 1 in 20 at the 95% level. CVaR, also called expected shortfall, is the average loss on the periods beyond the 97.5% (or 95%) level. Losses are computed from simple returns and shown as positive percentages.",
  "Daily figures use the daily returns. Monthly and quarterly figures use returns compounded over whole calendar months or quarters of the same days, never overlapping, with incomplete periods left out. Nothing is scaled up from daily by the square root of time.",
  "The panel shows two figures per level. Historical uses the observed returns directly and shows n/a when the sample holds too few tail observations. Forecast is the Cornish-Fisher figure: the Gaussian figure, which uses the average and the standard deviation of the returns, adjusted for skew and fat tails. Where Cornish-Fisher is n/a, because its formula is not valid there, the Forecast bar shows the Gaussian figure and carries a Gaussian tag. Where Cornish-Fisher VaR is n/a, its CVaR is n/a too. A figure is marked indicative when its formula passes the check only on the range it uses, or when it differs from the historical figure by more than half of it. It is shown, but it should not be read as precise.",
  "Each band is a 90% bootstrap band: the returns are resampled 1,000 times (in blocks for daily returns), and the band holds the middle 90% of the resulting figures. Bands for Gaussian and for historical VaR matched their coverage on simulated data; the others are marked approximate in the tooltip because they tend to be narrow.",
].join(" ");

const METHOD_LABEL: Record<TailMethod, string> = {
  historical: "Historical",
  gaussian: "Gaussian",
  cornish_fisher: "Cornish-Fisher",
};

/** "far from historical (10.2% vs 5.0%)" as a sentence. */
function sentence(text: string): string {
  return text.length === 0 ? text : text.charAt(0).toUpperCase() + text.slice(1);
}

/** What one bar stands for, in short sentences: shared by the tooltip and the table. */
function notesOf(bar: TailBar, digits: number, bandLevel: number): string[] {
  const f = bar.figure;
  if (f === undefined) return ["Not available."];
  if (f.value === null) return [sentence(f.reason ?? "Not available.")];
  const out: string[] = [];
  const approximate = f.band !== null && f.band_quality === "approximate";
  if (f.band) {
    out.push(`${bandName(bandLevel)} band ${loss(f.band.low, digits)} to ${loss(f.band.high, digits)}${approximate ? `, ${APPROXIMATE}` : ""}.`);
  } else {
    out.push(`No band${f.band_reason ? `: ${f.band_reason}` : ""}.`);
  }
  if (f.tail_count !== null) out.push(`${f.tail_count} observations in the tail; ${f.expected_tail_obs.toFixed(1)} expected.`);
  if (bar.key === "forecast") out.push(`Method: ${METHOD_LABEL[bar.source]}.`);
  if (bar.fallback) out.push(`${GAUSSIAN_NOTE}.`);
  if (f.indicative) out.push(`${INDICATIVE}: ${f.reason ?? "use with care"}.`);
  return out;
}

/** The name of a bar for the table: "VaR 95%, Forecast (Cornish-Fisher)". */
function barName(level: TailLevel, bar: TailBar): string {
  return bar.key === "forecast" ? `${level.label}, ${bar.label} (${METHOD_LABEL[bar.source]})` : `${level.label}, ${bar.label}`;
}

function InfoIcon() {
  return (
    <svg className="tr-info" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <circle cx="10" cy="10" r="7.5" />
      <path d="M10 9v5M10 6.2v.2" />
    </svg>
  );
}

function CautionIcon() {
  return (
    <svg className="tr-ind-ic" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path d="M10 2.8 18 16.8H2z" />
      <path d="M10 8v4M10 14.4v.3" />
    </svg>
  );
}

/** The cells of one table row, for assistive technology only. */
function Cells({ name, bar, digits, bandLevel }: { name: string; bar: TailBar; digits: number; bandLevel: number }) {
  const f = bar.figure;
  const value = f?.value ?? null;
  const band = f?.band ?? null;
  return (
    <>
      <span role="rowheader" className="vh">
        {name}
      </span>
      <span role="cell" className="vh">
        {value === null ? "n/a" : loss(value, digits)}
      </span>
      <span role="cell" className="vh">
        {band ? `${loss(band.low, digits)} to ${loss(band.high, digits)}` : "no band"}
      </span>
      <span role="cell" className="vh">
        {notesOf(bar, digits, bandLevel).join(" ")}
      </span>
    </>
  );
}

/** Moves between the bars with the arrow keys (one tab stop for the chart); Escape hides the tooltip. */
function onKey(e: KeyboardEvent<HTMLElement>) {
  const row = e.currentTarget;
  if (e.key === "Escape") {
    row.dataset.esc = "1";
    return;
  }
  const rows = Array.from(row.closest(".tr-chart")?.querySelectorAll<HTMLElement>(".tr-row") ?? []);
  const at = rows.indexOf(row);
  const to =
    e.key === "ArrowDown" ? at + 1 : e.key === "ArrowUp" ? at - 1 : e.key === "Home" ? 0 : e.key === "End" ? rows.length - 1 : at;
  const target = rows[to];
  if (to !== at && target !== undefined) {
    e.preventDefault();
    target.focus();
  }
}

interface BarRowProps {
  level: TailLevel;
  bar: TailBar;
  scale: Scale;
  digits: number;
  bandLevel: number;
  horizon: Horizon;
  tabbable: boolean;
  onFocusRow: () => void;
}

function BarRow({ level, bar, scale, digits, bandLevel, horizon, tabbable, onFocusRow }: BarRowProps) {
  const f = bar.figure;
  const value = f?.value ?? null;
  const name = barName(level, bar);
  const notes = notesOf(bar, digits, bandLevel);
  const band = f?.band ?? null;
  const indicative = f?.indicative === true && value !== null;
  const zero = place(0, scale);
  const at = value === null ? 0 : place(value, scale);
  const end = Math.max(at, band ? place(band.high, scale) : at);
  return (
    <div
      role="row"
      className="tr-row"
      data-bar={bar.key}
      tabIndex={tabbable ? 0 : -1}
      onFocus={onFocusRow}
      onKeyDown={onKey}
      onBlur={(e) => delete e.currentTarget.dataset.esc}
      onMouseLeave={(e) => delete e.currentTarget.dataset.esc}
    >
      <Cells name={name} bar={bar} digits={digits} bandLevel={bandLevel} />
      <div className="tr-track" aria-hidden="true">
        {value === null ? (
          <span className="tr-na">
            <i />
            n/a
            <InfoIcon />
          </span>
        ) : (
          <>
            {band ? (
              <i
                className="tr-band"
                style={{ left: `${place(band.low, scale)}%`, width: `${place(band.high, scale) - place(band.low, scale)}%` }}
              />
            ) : null}
            <i
              className={indicative ? "tr-bar ind" : "tr-bar"}
              style={{ left: `${Math.min(zero, at)}%`, width: `${Math.abs(at - zero)}%` }}
            />
            <span className="tr-val" style={{ left: `${end}%` }}>
              {loss(value, digits)}
              {indicative ? <CautionIcon /> : null}
              {bar.fallback ? <span className="tr-tag">{GAUSSIAN}</span> : null}
              {band === null ? <InfoIcon /> : null}
            </span>
          </>
        )}
      </div>
      <span className="tr-tip" aria-hidden="true">
        <b>{name}</b>
        <span>{value === null ? "No figure." : `Estimate ${loss(value, digits)}.`}</span>
        <span>{`${whatItMeans(level.measure, level.level, horizon)}.`}</span>
        {notes.map((n) => (
          <span key={n}>{n}</span>
        ))}
      </span>
    </div>
  );
}

/** The methods that no bar shows: Gaussian beside a Cornish-Fisher Forecast, or Cornish-Fisher beside a Gaussian one. */
function hiddenMethods(level: TailLevel): TailMethod[] {
  const shown = level.bars[1].source;
  return (["gaussian", "cornish_fisher"] as const).filter((m) => m !== shown);
}

interface ChartProps {
  groups: TailGroup[];
  scale: Scale;
  digits: number;
  bandLevel: number;
  horizon: Horizon;
}

function Chart({ groups, scale, digits, bandLevel, horizon }: ChartProps) {
  const [cursor, setCursor] = useState(0);
  const ticks = ticksOf(scale);
  const unit = horizonInfo(horizon).many;
  const total = groups.reduce((n, g) => n + g.levels.length * 2, 0);
  const current = Math.min(cursor, Math.max(0, total - 1));
  const hasTag = groups.some((g) => g.levels.some((l) => l.bars[1].fallback));
  const style = { "--tr-end": hasTag ? "128px" : "72px" } as CSSProperties;
  let index = 0;
  return (
    <div className="tr-chart" role="table" aria-label="Value at risk and CVaR by level, Historical and Forecast" style={style}>
      <div role="row" className="vh">
        <span role="columnheader">Level and method</span>
        <span role="columnheader">Estimate</span>
        <span role="columnheader">Band</span>
        <span role="columnheader">Notes</span>
      </div>
      <div className="tr-grid" aria-hidden="true">
        {ticks.map((t) => (
          <i key={t} className={t === 0 ? "zero" : undefined} style={{ left: `${place(t, scale)}%` }} />
        ))}
      </div>
      {groups.map((g) => (
        <div key={g.measure} role="rowgroup" aria-label={g.label} className="tr-group">
          <div className="tr-gh" aria-hidden="true">
            <b>{g.label}</b>
            <span>{g.measure === "var" ? `Loss exceeded on only the worst ${unit}` : `Average loss on the worst ${unit}`}</span>
          </div>
          {g.levels.map((l) => (
            <div key={l.key} className="tr-level">
              <div className="tr-lv" aria-hidden="true">
                <b>{levelName(l.level)}</b>
                <span>{oneIn(l.level, horizon)}</span>
              </div>
              <div className="tr-bars">
                {l.bars.map((b) => {
                  const i = index++;
                  return (
                    <BarRow
                      key={b.key}
                      level={l}
                      bar={b}
                      scale={scale}
                      digits={digits}
                      bandLevel={bandLevel}
                      horizon={horizon}
                      tabbable={i === current}
                      onFocusRow={() => setCursor(i)}
                    />
                  );
                })}
                {hiddenMethods(l).map((m) => (
                  <div role="row" className="vh" key={m}>
                    <Cells
                      name={`${l.label}, ${METHOD_LABEL[m]}`}
                      bar={{ key: "historical", label: METHOD_LABEL[m], figure: l.cells[m], source: m, fallback: false }}
                      digits={digits}
                      bandLevel={bandLevel}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ))}
      <div className="tr-axis" aria-hidden="true">
        <span className="tr-axis-t">Loss, % of value</span>
        {ticks.map((t) => (
          <span key={t} style={{ left: `${place(t, scale)}%` }}>
            {tickText(t)}
          </span>
        ))}
      </div>
    </div>
  );
}

function Legend({ groups, bandLevel }: { groups: TailGroup[]; bandLevel: number }) {
  const bars = groups.flatMap((g) => g.levels.flatMap((l) => l.bars));
  const anyIndicative = bars.some((b) => b.figure?.indicative === true && b.figure.value !== null);
  const anyTag = bars.some((b) => b.fallback);
  return (
    <ul className="tr-legend" aria-label="How to read the chart">
      <li data-bar="historical">
        <i className="tr-sw" />
        Historical
      </li>
      <li data-bar="forecast">
        <i className="tr-sw" />
        Forecast (Cornish-Fisher)
      </li>
      <li>
        <i className="tr-sw-band" />
        {bandName(bandLevel)} band from resampling
      </li>
      {anyIndicative ? (
        <li>
          <CautionIcon />
          Indicative: use with care
        </li>
      ) : null}
      {anyTag ? (
        <li>
          <span className="tr-tag">{GAUSSIAN}</span>
          Shown where Cornish-Fisher is n/a
        </li>
      ) : null}
    </ul>
  );
}

/** What a horizon shows: its two groups, the one shared scale and the decimals that scale needs. */
function viewOf(horizon: TailHorizon) {
  const groups = groupsOf(horizon.figures ?? []);
  const scale = scaleOf(shownFigures(groups));
  return { groups, scale, digits: digitsFor(scale), bandLevel: horizon.series?.band_level ?? 0.9 };
}

function Lines({ horizon }: { horizon: TailHorizon }) {
  const { groups, scale, digits, bandLevel } = viewOf(horizon);
  return (
    <div className="tr-lines">
      <Legend groups={groups} bandLevel={bandLevel} />
      <Chart groups={groups} scale={scale} digits={digits} bandLevel={bandLevel} horizon={horizon.horizon} />
    </div>
  );
}

/** "8.6% (6.4% to 10.6%)", or "n/a". */
function figureText(f: TailFigure | undefined, digits: number): string {
  if (f === undefined || f.value === null) return "n/a";
  return f.band ? `${loss(f.value, digits)} (${loss(f.band.low, digits)} to ${loss(f.band.high, digits)})` : `${loss(f.value, digits)} (no band)`;
}

/** The method text, then every method of every level with its band: Gaussian is listed here and in the table only. */
function How({ horizon }: { horizon: TailHorizon }) {
  if (horizon.status !== "ok") return <>{HOW}</>;
  const { groups, digits, bandLevel } = viewOf(horizon);
  return (
    <>
      {HOW}
      <span className="tr-all">
        <span className="tr-all-t">All three methods, with their {bandName(bandLevel)} bands</span>
        {groups.flatMap((g) =>
          g.levels.map((l) => (
            <span key={l.key} className="tr-all-row">
              <b>{l.label}</b> {METHODS.map((m) => `${m.label} ${figureText(l.cells[m.key], digits)}`).join("; ")}
            </span>
          )),
        )}
      </span>
    </>
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
      how={<How horizon={current} />}
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
 * section is absent (null). One grouped chart on one shared axis: a VaR group and a CVaR group, one
 * level per row, each with a Historical and a Forecast bar (Cornish-Fisher, or Gaussian where that is
 * n/a), with a Daily | Monthly | Quarterly switch (monthly records have no daily horizon); the switch
 * starts on the series' own frequency. The chart is also a table for assistive technology, and that
 * table holds the Gaussian and Cornish-Fisher figures that no bar shows.
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
