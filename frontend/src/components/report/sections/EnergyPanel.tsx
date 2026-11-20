import type { EnergyModel, EnergyRow, EnergySection, FactorReport } from "../../../api/types";
import { count, dateLong, dateShort, num, pct, pval, signed, tstat } from "../../../format";
import { observations } from "../../../report/subject";
import { position } from "../../charts/BarCell";
import { niceDomain, tickLabel, valueDigits } from "../exposureModel";
import type { NiceDomain } from "../exposureModel";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import "./EnergyPanel.css";

export const TITLE = "Energy & carbon";
export const QUESTION = "How has the return moved with oil, gas and carbon prices, after the market?";
/** One line above the tables; the method detail is in "How this is computed". */
export const INTRO =
  "Each number describes how the return moved together with that price, not what comes next.";
/** Two-sided 95% normal quantile, for the line beta ± 1.96 · SE. */
const Z95 = 1.96;
/** A variance inflation factor above this gets the caution style (the bar of the main regression). */
export const VIF_WARN = 5;
/** The size of the price rise in the plain-words sentences. */
export const RISE = 0.1;

function finite(x: number | null | undefined): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

/** The approximate 95% range of a sensitivity. Null without a usable standard error. */
export function whisker(row: { beta: number; se: number }): { low: number; high: number } | null {
  if (!finite(row.beta) || !finite(row.se)) return null;
  return { low: row.beta - Z95 * row.se, high: row.beta + Z95 * row.se };
}

/** True when the leg's variance inflation factor is above the warning bar. */
export function overlaps(row: Pick<EnergyRow, "vif">): boolean {
  return finite(row.vif) && row.vif > VIF_WARN;
}

/**
 * The move of the subject, as a fraction, that went with a 10% rise in the leg. Oil and gas are
 * log changes of the price, so a 10% rise is ln(1.10); carbon is a plain return, so it is 0.10.
 */
export function moveFor(code: EnergyRow["code"], beta: number): number {
  return code === "co2" ? beta * RISE : beta * Math.log(1 + RISE);
}

const NOUNS: Readonly<Record<string, string>> = {
  oil: "oil",
  gas: "natural gas",
  co2: "carbon credits (KRBN)",
};

/** "A 10% rise in oil went with a +2.1% move in SPY, after the market." Null for the market row. */
export function sentence(row: Pick<EnergyRow, "code" | "beta" | "tag">, subject: string): string | null {
  const noun = NOUNS[row.code];
  if (noun === undefined) return null;
  const move = pct(moveFor(row.code, row.beta), 1);
  const base = `A ${pct(RISE, 0, false)} rise in ${noun} went with a ${move} move in ${subject}, after the market`;
  return row.tag === "reliable" ? `${base}.` : `${base}. The link is too weak to rely on.`;
}

function tickText(t: number, ticks: readonly number[]): string {
  return tickLabel(t, ticks, 2);
}

/** A sensitivity with at least two significant digits and at least three decimals: "0.0021", "0.412". */
function betaText(x: number): string {
  return signed(x, valueDigits(x, 3));
}

function wordFor(s: EnergySection): string {
  return s.frequency === "monthly" ? "months" : "days";
}

function textOf(label: string, row: { beta: number; se: number }): string {
  const w = whisker(row);
  const tail = w ? `, approximate 95% range ${betaText(w.low)} to ${betaText(w.high)}` : "";
  return `${label}: sensitivity ${betaText(row.beta)}${tail}`;
}

/** The first dates of the series behind the legs, in words. */
function legsText(s: EnergySection): string {
  return s.legs
    .map((l) => `${l.ticker} from ${l.first_date ? dateLong(l.first_date) : "an unknown date"}`)
    .join(", ");
}

function limitText(model: EnergyModel): string {
  return model.window_limited_by
    ? `${model.title}: the window starts when ${model.window_limited_by} begins, which is later than the start of the data.`
    : "";
}

function modelHow(model: EnergyModel): string {
  const vifs = model.rows.map((r) => `${r.label} ${num(r.vif, 2)}`).join(", ");
  const tags = model.rows.map((r) => `${r.label} ${r.tag}, p ${pval(r.p)}`).join("; ");
  const dates = model.gas_robust.excluded_dates.map((d) => dateLong(d)).join(", ");
  return [
    `${model.title}: ${dateLong(model.start)} to ${dateLong(model.end)}, ${count(model.n_obs)} observations.`,
    model.r2 != null && model.adj_r2 != null ? `R² ${num(model.r2, 3)}, adjusted R² ${num(model.adj_r2, 3)}.` : "",
    `Overlap between the legs (variance inflation factor): ${vifs}.`,
    `Tag of each leg (Benjamini-Hochberg across the legs of this model): ${tags}.`,
    `Without the largest gas moves: the ${model.gas_robust.n_excluded} rows with the largest absolute gas change are left out (${dates}) and the model is fitted again on ${count(model.gas_robust.n_obs)} observations. Nothing is trimmed or capped.`,
    limitText(model),
  ]
    .filter((p) => p !== "")
    .join(" ");
}

function how(s: EnergySection, rows: string): string {
  const models = [s.long_model, s.carbon_model].filter((m): m is EnergyModel => m != null);
  const first = models[0];
  const reference =
    first?.t_reference === "student_t"
      ? "p-values use the Student-t reference with a small-sample correction (monthly data)"
      : "p-values use the normal reference";
  const defs = new Map<string, string>();
  for (const m of models) for (const r of m.rows) defs.set(r.code, `${r.label} = ${r.definition}${r.note ? ` (${r.note})` : ""}`);
  return [
    s.model_note,
    `Each model is fitted by least squares on the same ${rows} for every leg, with Newey-West standard errors (${first?.hac_lags ?? 0} lags); ${reference}. No lagged terms are used: tests on oil, gas and carbon found none that matter.`,
    "The dot is the sensitivity and the line is its approximate 95% range, all on one scale with a line at zero. Oil and gas come from the first model; carbon comes from the second, shorter model, which also controls for oil and gas. The market is a control in both and has no row.",
    `Legs: ${Array.from(defs.values()).join("; ")}.`,
    s.gas_note,
    ...models.map(modelHow),
    s.carbon_note ? `Carbon: ${s.carbon_note}` : "",
    s.fred_note ? `Data: ${s.fred_note}` : "",
    `Series start: ${legsText(s)}.`,
    `${count(s.n_sample - (s.long_model?.n_obs ?? 0))} of ${count(s.n_sample)} rows of the analysis sample are left out of the first model because oil or gas has no value there.`,
  ]
    .filter((p) => p !== "")
    .join(" ");
}

function Plot({ label, row, domain }: { label: string; row: { beta: number; se: number }; domain: NiceDomain }) {
  const { lo, hi, ticks } = domain;
  const w = whisker(row);
  const a = w ? position(w.low, lo, hi) : 0;
  const b = w ? position(w.high, lo, hi) : 0;
  return (
    <svg className="bar-svg" aria-hidden="true">
      <title>{textOf(label, row)}</title>
      {ticks.map((t) => {
        const x = `${position(t, lo, hi)}%`;
        return <line key={t} className={Math.abs(t) < 1e-12 ? "zero" : "grid"} x1={x} x2={x} y1="0" y2="100%" />;
      })}
      {w ? (
        <>
          <line className="ci" x1={`${a}%`} x2={`${b}%`} y1="50%" y2="50%" />
          {b - a >= 1.2 ? (
            <>
              <line className="ci" x1={`${a}%`} x2={`${a}%`} y1="40%" y2="60%" />
              <line className="ci" x1={`${b}%`} x2={`${b}%`} y1="40%" y2="60%" />
            </>
          ) : null}
        </>
      ) : null}
      {finite(row.beta) ? <circle className="en-dot" cx={`${position(row.beta, lo, hi)}%`} cy="50%" r="4" /> : null}
    </svg>
  );
}

/** One row of the table: a leg of the long model, or the carbon leg of the carbon model. */
interface Leg {
  code: EnergyRow["code"];
  label: string;
  note: string | null;
  title: string;
  beta: number;
  se: number;
  t: number;
  tag: EnergyRow["tag"];
  vif: number;
}

/**
 * The legs shown in the table: oil and gas from the long model, and carbon from the carbon model.
 * The market is a control in both models and gets no row; the full numbers of each model are in
 * "How this is computed".
 */
export function legsOf(s: EnergySection): Leg[] {
  const leg = (r: EnergyRow, note: string | null): Leg => ({
    code: r.code,
    label: r.label,
    note,
    title: `${r.definition}${r.note ? `; ${r.note}` : ""}`,
    beta: r.beta,
    se: r.se,
    t: r.t,
    tag: r.tag,
    vif: r.vif,
  });
  const legs = (s.long_model?.rows ?? []).filter((r) => r.code !== "mkt_rf").map((r) => leg(r, null));
  const co2 = s.carbon_model?.rows.find((r) => r.code === "co2");
  if (s.carbon_model && co2) legs.push(leg(co2, s.carbon_model.label ?? co2.note));
  return legs;
}

function domainOfLegs(legs: readonly Leg[]): NiceDomain {
  const values = [0];
  for (const row of legs) {
    if (finite(row.beta)) values.push(row.beta);
    const w = whisker(row);
    if (w) values.push(w.low, w.high);
  }
  return niceDomain(Math.min(...values), Math.max(...values), 3);
}

/** "Natural gas and carbon credits (KRBN): no link strong enough to rely on." Null when every leg is reliable. */
export function weakLine(legs: readonly Pick<Leg, "code" | "tag">[]): string | null {
  const names = legs.filter((l) => l.tag !== "reliable").map((l) => NOUNS[l.code] ?? l.code);
  if (names.length === 0) return null;
  const list = names.length === 1 ? (names[0] ?? "") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  return `${list.charAt(0).toUpperCase()}${list.slice(1)}: no link strong enough to rely on, after the market.`;
}

function Line({ leg, domain }: { leg: Leg; domain: NiceDomain }) {
  const { label, note, title, beta, se, t } = leg;
  return (
    <tr data-leg={leg.code}>
      <th scope="row" title={title}>
        <span className="en-label">{label}</span>
        {note ? <span className="en-note">{note}</span> : null}
      </th>
      <td className="num">{finite(beta) ? betaText(beta) : "n/a"}</td>
      <td className="en-plot">
        <Plot label={label} row={{ beta, se }} domain={domain} />
        <span className="vh">{textOf(label, { beta, se })}</span>
      </td>
      <td className="num">{finite(t) ? tstat(t) : "n/a"}</td>
    </tr>
  );
}

function Legs({ s, subject, rows }: { s: EnergySection; subject: string; rows: string }) {
  const legs = legsOf(s);
  const domain = domainOfLegs(legs);
  const says = legs.filter((l) => l.tag === "reliable").map((l) => sentence(l, subject)).filter((x): x is string => x !== null);
  const gas = s.long_model?.gas_robust;
  const gasLeg = legs.find((l) => l.code === "gas");
  if (gas && gasLeg?.tag === "reliable") {
    says.push(`Without the ${gas.n_excluded} largest gas ${wordFor(s)}, the same rise in gas goes with a ${pct(moveFor("gas", gas.beta), 1)} move.`);
  }
  const weak = weakLine(legs);
  if (weak) says.push(weak);
  const crowded = legs.filter(overlaps);
  const limited = s.long_model?.window_limited_by;
  return (
    <div className="en-model">
      <div className="en-wrap">
        <table className="en-table">
          <caption className="vh">
            Sensitivity of the return to oil, gas and carbon after the market, with an approximate 95% range and its t-statistic, on {rows}
          </caption>
          <thead>
            <tr>
              <th scope="col">Price</th>
              <th scope="col" className="num">
                Sensitivity
              </th>
              <th scope="col" className="en-plot-h">
                <span className="vh">Chart: sensitivity and approximate 95% range</span>
              </th>
              <th scope="col" className="num">
                t
              </th>
            </tr>
          </thead>
          <tbody>
            {legs.map((l) => (
              <Line key={l.code} leg={l} domain={domain} />
            ))}
          </tbody>
          <tfoot aria-hidden="true">
            <tr>
              <td />
              <td />
              <td className="en-axis">
                <div className="axis">
                  {domain.ticks.map((t) => (
                    <span key={t} style={{ left: `${position(t, domain.lo, domain.hi)}%` }}>
                      {tickText(t, domain.ticks)}
                    </span>
                  ))}
                </div>
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      <ul className="en-says">
        {says.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {crowded.length > 0 ? (
        <p className="en-limit en-overlap">
          {crowded.map((l) => l.label).join(" and ")} overlap{crowded.length === 1 ? "s" : ""} with the other prices
          (variance inflation factor above {VIF_WARN}), so the sensitivity is imprecise.
        </p>
      ) : null}
      {limited && s.long_model ? (
        <p className="en-limit">
          The window starts when {limited} begins ({dateLong(s.long_model.start)}).
        </p>
      ) : null}
    </div>
  );
}

/**
 * Panel of the `energy` section (S3-8): how the return moved with oil, gas and carbon prices after
 * the market. One table with one row per price: oil and gas from the long model, carbon from the
 * short carbon model. Each row has the sensitivity, a dot and an approximate 95% range on one scale,
 * and the t-statistic. Plain-words sentences for the reliable legs and one line for the weak ones.
 * The market rows, the VIFs and the gas fit without the largest moves are in "How this is computed";
 * an overlap above the VIF bar gets a caution line. Registered in `panelRegistry.ts` at position 509,
 * right after Macro sensitivities. Renders nothing when the section is absent; a section that could
 * not be computed shows its reason (for example FRED being down) and nothing else.
 */
export function EnergyPanel({ report }: ReportPanelProps) {
  const s: FactorReport["energy"] = report.energy;
  if (s == null) return null;
  if (s.status !== "ok" || s.long_model == null) {
    return (
      <Panel
        id="energy"
        title={TITLE}
        question={QUESTION}
        empty={{
          reason: s.reason ?? "The energy and carbon sensitivities could not be computed for this range.",
          action: "The rest of the report is not affected.",
        }}
      />
    );
  }
  const rows = observations(report, s.long_model.n_obs);
  const start = s.long_model.start;
  const end = s.long_model.end;
  const subject = report.ticker;
  return (
    <Panel
      id="energy"
      title={TITLE}
      question={QUESTION}
      aside={`${dateShort(start)} to ${dateShort(end)}`}
      reading={INTRO}
      footnote={s.gas_note}
      how={how(s, rows)}
    >
      <Legs s={s} subject={subject} rows={rows} />
      {s.fred_note ? <p className="en-carbon-note en-fred-note">{s.fred_note}</p> : null}
      {s.carbon_model == null && s.carbon_note ? <p className="en-carbon-note">{s.carbon_note}</p> : null}
    </Panel>
  );
}
