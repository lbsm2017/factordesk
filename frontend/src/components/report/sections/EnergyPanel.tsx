import type { EnergyModel, EnergyRow, EnergySection, FactorReport } from "../../../api/types";
import { count, dateLong, dateShort, num, pct, pval, signed, tstat } from "../../../format";
import { observations } from "../../../report/subject";
import { position } from "../../charts/BarCell";
import { niceDomain } from "../exposureModel";
import type { NiceDomain } from "../exposureModel";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import "./EnergyPanel.css";

export const TITLE = "Energy & carbon";
export const QUESTION = "How has the return moved with oil, gas and carbon prices, after the market?";
/** One line above the tables; the method detail is in "How this is computed". */
export const INTRO =
  "Sensitivities to oil, gas and carbon prices, with the market taken out. They describe how the return moved together with each price, not what comes next.";
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

function domainOf(model: EnergyModel): NiceDomain {
  const values = [0];
  const parts = [...model.rows.filter((r) => r.code !== "mkt_rf"), model.gas_robust];
  for (const row of parts) {
    if (finite(row.beta)) values.push(row.beta);
    const w = whisker(row);
    if (w) values.push(w.low, w.high);
  }
  return niceDomain(Math.min(...values), Math.max(...values), 3);
}

function tickText(t: number): string {
  if (Math.abs(t) < 1e-12) return "0";
  return num(t, Math.abs(t) >= 1 && Number.isInteger(t) ? 0 : 2);
}

function wordFor(s: EnergySection): string {
  return s.frequency === "monthly" ? "months" : "days";
}

function robustLabel(s: EnergySection, model: EnergyModel): string {
  return `Natural gas without the ${model.gas_robust.n_excluded} largest ${wordFor(s)}`;
}

function textOf(label: string, row: { beta: number; se: number }): string {
  const w = whisker(row);
  const tail = w ? `, approximate 95% range ${signed(w.low, 3)} to ${signed(w.high, 3)}` : "";
  return `${label}: sensitivity ${signed(row.beta, 3)}${tail}`;
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
    "The dot is the sensitivity and the line is its approximate 95% range. All rows of a model share one scale, with a line at zero. The market row is a control and has no chart.",
    `Legs: ${Array.from(defs.values()).join("; ")}.`,
    s.gas_note,
    ...models.map(modelHow),
    s.carbon_note ? `Carbon: ${s.carbon_note}` : "",
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

function Vif({ row }: { row: Pick<EnergyRow, "vif"> }) {
  return (
    <span
      className={overlaps(row) ? "en-vif warn" : "en-vif"}
      title={`Variance inflation factor ${num(row.vif, 2)}: how much this leg overlaps with the other legs. Above ${VIF_WARN} means its sensitivity is imprecise.`}
    >
      {num(row.vif, 2)}
    </span>
  );
}

interface LineProps {
  label: string;
  note?: string | null;
  title: string;
  beta: number;
  se: number;
  t: number;
  domain: NiceDomain;
  chart: boolean;
  vif?: number;
  variant?: string;
}

function Line({ label, note, title, beta, se, t, domain, chart, vif, variant }: LineProps) {
  return (
    <tr className={variant}>
      <th scope="row" title={title}>
        <span className="en-label">{label}</span>
        {note ? <span className="en-note">{note}</span> : null}
      </th>
      <td className="num">{finite(beta) ? signed(beta, 3) : "n/a"}</td>
      <td className="en-plot">
        {chart ? (
          <>
            <Plot label={label} row={{ beta, se }} domain={domain} />
            <span className="vh">{textOf(label, { beta, se })}</span>
          </>
        ) : (
          <span className="en-control">controlled for</span>
        )}
      </td>
      <td className="num">{finite(t) ? tstat(t) : "n/a"}</td>
      <td className="num en-vif-cell">{vif !== undefined ? <Vif row={{ vif }} /> : null}</td>
    </tr>
  );
}

function Model({ s, model, subject, rows }: { s: EnergySection; model: EnergyModel; subject: string; rows: string }) {
  const domain = domainOf(model);
  const says = model.rows.map((r) => sentence(r, subject)).filter((x): x is string => x !== null);
  const gas = model.gas_robust;
  const gasRow = model.rows.find((r) => r.code === "gas");
  return (
    <div className="en-model" data-model={model.key}>
      <div className="en-model-head">
        <h3>{model.title}</h3>
        {model.label ? <span className="en-tag">{model.label}</span> : null}
        <span className="en-span">
          {dateShort(model.start)} to {dateShort(model.end)}
        </span>
      </div>
      <div className="en-wrap">
        <table className="en-table">
          <caption className="vh">
            Sensitivity of the return to each leg with an approximate 95% range, its t-statistic and its overlap with the other legs, {model.title}, on {rows}
          </caption>
          <thead>
            <tr>
              <th scope="col">Leg</th>
              <th scope="col" className="num">
                Sensitivity
              </th>
              <th scope="col" className="en-plot-h">
                <span className="vh">Chart: sensitivity and approximate 95% range</span>
              </th>
              <th scope="col" className="num">
                t
              </th>
              <th scope="col" className="num">
                <abbr title="Variance inflation factor: how much a leg overlaps with the other legs. 1 means none.">VIF</abbr>
              </th>
            </tr>
          </thead>
          <tbody>
            {model.rows.flatMap((r) => {
              const title = `${r.definition}${r.note ? `; ${r.note}` : ""}`;
              const main = (
                <Line
                  key={r.code}
                  label={r.label}
                  note={r.code === "gas" && s.frequency === "daily" ? `${r.note ?? "fat-tailed"}; daily figures are descriptive` : r.note}
                  title={title}
                  beta={r.beta}
                  se={r.se}
                  t={r.t}
                  domain={domain}
                  chart={r.code !== "mkt_rf"}
                  vif={r.vif}
                />
              );
              if (r.code !== "gas") return [main];
              return [
                main,
                <Line
                  key="gas-robust"
                  label={robustLabel(s, model)}
                  title={`The same model fitted again without the ${gas.n_excluded} rows with the largest absolute gas change`}
                  beta={gas.beta}
                  se={gas.se}
                  t={gas.t}
                  domain={domain}
                  chart
                  variant="en-robust"
                />,
              ];
            })}
          </tbody>
          <tfoot aria-hidden="true">
            <tr>
              <td />
              <td />
              <td className="en-axis">
                <div className="axis">
                  {domain.ticks.map((t) => (
                    <span key={t} style={{ left: `${position(t, domain.lo, domain.hi)}%` }}>
                      {tickText(t)}
                    </span>
                  ))}
                </div>
              </td>
              <td />
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      <ul className="en-says">
        {says.map((line) => (
          <li key={line}>{line}</li>
        ))}
        {gasRow ? (
          <li>
            {`Without the ${gas.n_excluded} largest gas ${wordFor(s)}, the same rise in gas goes with a ${pct(moveFor("gas", gas.beta), 1)} move.`}
          </li>
        ) : null}
      </ul>
      {model.window_limited_by ? (
        <p className="en-limit">
          The window starts when {model.window_limited_by} begins ({dateLong(model.start)}).
        </p>
      ) : null}
    </div>
  );
}

/**
 * Panel of the `energy` section (S3-8): how the return moved with oil, gas and carbon prices after
 * the market. One table per model (market, oil and gas; and, on a short sample, market, oil, gas and
 * carbon), with the sensitivity, a dot and an approximate 95% range on one scale, the t-statistic,
 * the VIF of every leg, the gas sensitivity again without the five largest gas moves, and
 * plain-words sentences. Registered in `panelRegistry.ts` at position 509, right after Macro
 * sensitivities. Renders nothing when the section is absent; a section that could not be computed
 * shows its reason (for example FRED being down) and nothing else.
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
      <Model s={s} model={s.long_model} subject={subject} rows={rows} />
      {s.carbon_model ? <Model s={s} model={s.carbon_model} subject={subject} rows={observations(report, s.carbon_model.n_obs)} /> : null}
      {s.carbon_model == null && s.carbon_note ? <p className="en-carbon-note">{s.carbon_note}</p> : null}
    </Panel>
  );
}
