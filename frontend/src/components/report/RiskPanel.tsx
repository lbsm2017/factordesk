/* eslint-disable jsx-a11y/no-redundant-roles, jsx-a11y/no-interactive-element-to-noninteractive-role --
   DB7 asks for explicit table roles: the narrow-screen CSS restyles rows as grids, which can drop table semantics. */
import { riskOutcome } from "../../text/outcome";
import { PLAIN } from "../../text/plain";
import { useShowStats } from "../../state/stats";
import { isSubjectReport, stepWord } from "../../report/subject";
import { describe, factorOrder, finite, IDIO, labelTexts, sci, slotOf } from "../../report/derive";
import { BarCell } from "../charts/BarCell";
import { AxisRow, KeySwatch, NameCell, pctN, signedN } from "./barParts";
import { Panel } from "./Panel";
import type { ReportPanelProps } from "./types";

const EMPTY_ACTION = "Widen the date range and run the report again.";

/** Panel 7: where the risk comes from (Euler share of variance per factor, stock-specific hatched). */
export function RiskPanel({ report }: ReportPanelProps) {
  const stats = useShowStats();
  const rk = report.risk_contribution;
  const title = "Risk sources";
  const question = `What share of the ${stepWord(report)} variance does each factor drive?`;

  const shares = new Map<string, number | null>(Object.entries(rk.factors).map(([n, v]) => [n, finite(v)]));
  shares.set(IDIO, finite(rk.idiosyncratic));
  const names = rk.order.filter((n) => shares.has(n));
  for (const n of shares.keys()) if (!names.includes(n) && n !== IDIO) names.push(n);
  if (!names.includes(IDIO)) names.push(IDIO);
  const values = [...shares.values()].flatMap((v) => (v === null ? [] : [v]));

  if (rk.status !== "ok") {
    return (
      <Panel
        id="risk"
        title={title}
        question={question}
        empty={{ reason: rk.reason ?? "The risk attribution could not be computed.", action: EMPTY_ACTION }}
      />
    );
  }
  if (values.length === 0) {
    return (
      <Panel
        id="risk"
        title={title}
        question={question}
        empty={{ reason: "Insufficient data: no risk attribution available.", action: EMPTY_ACTION }}
      />
    );
  }

  // Subject-neutral words for an uploaded record or a portfolio; a ticker keeps the stock wording.
  const specific = isSubjectReport(report) ? "specific to this record" : "stock-specific";
  const specificLabel = isSubjectReport(report) ? "Specific to this record" : "Stock-specific";
  const order = factorOrder(report);
  const details = new Map(rk.details.map((d) => [d.name, d]));
  // Shares add to 100%: ticks at 0, 50% and 100% keep the labels apart in the half-width panel; the plot
  // extends a little to the left of zero when a factor offsets the others.
  const lo = Math.min(0, ...values) < 0 ? Math.floor(Math.min(...values) * 20) / 20 : 0;
  const hi = Math.max(1, ...values);
  const ticks = [0, 0.5, 1];

  const vol = finite(rk.total_vol_annual);
  const reading = [vol !== null ? `Total volatility is ${pctN(vol, 1, false)} a year.` : "", ...rk.sentences]
    .filter(Boolean)
    .join(" ");

  const sumRes = finite(rk.sums_to_one_residual);
  const how = [
    rk.caption,
    "Euler decomposition of variance: share = beta x factor volatility x correlation with the factor-driven return, divided by total volatility.",
    ...labelTexts(report, rk.labels),
    sumRes !== null ? `Sum check ${sci(sumRes)}.` : "",
  ]
    .filter(Boolean)
    .join(" ");
  const desc = describe(report);

  return (
    <Panel
      id="risk"
      title={title}
      question={question}
      outcome={riskOutcome(report)}
      reading={reading || undefined}
      footnote={`${desc} Shares add to 100% and can be negative when a factor offsets the others.`}
      how={how}
    >
      <table role="table" className={stats ? "bars cols-4 risk" : "bars risk"}>
        <caption className="vh">
          Share of variance per factor and {specific}, with exposure, factor volatility and correlation
        </caption>
        <thead role="rowgroup">
          <tr role="row">
            <th role="columnheader" scope="col">
              Source
            </th>
            <th role="columnheader" scope="col" className="plot-h">
              <span className="vh">Chart</span>
            </th>
            <th role="columnheader" scope="col" className="num">
              Share
            </th>
            {stats
              ? ["Beta", "Factor vol", "Corr."].map((h) => (
                  <th key={h} role="columnheader" scope="col" className="num">
                    {h}
                  </th>
                ))
              : null}
          </tr>
        </thead>
        <tbody role="rowgroup">
          {names.map((name) => {
            const v = shares.get(name) ?? null;
            const d = details.get(name);
            const idio = name === IDIO;
            const slot = slotOf(name, order);
            const key = idio ? "hatch" : `cat c${slot}`;
            let title: string;
            let mobile = "";
            let cells: string[];
            if (idio) {
              title = `Idiosyncratic: ${pctN(v, 2, false)} of variance`;
              mobile = "Not explained by the factors";
              cells = ["–", "–", "–"];
            } else if (!d) {
              title = `${name}: ${pctN(v, 2, false)} of variance`;
              cells = ["n/a", "n/a", "n/a"];
            } else {
              title =
                `${name}: ${pctN(v, 2, false)} of variance = exposure ${signedN(d.beta)} x volatility ` +
                `${pctN(d.sigma_annual, 1, false)} x correlation ${signedN(d.rho_sys, 2)} with the factor-driven return`;
              mobile = `Beta ${signedN(d.beta)}, vol ${pctN(d.sigma_annual, 1, false)}, corr ${signedN(d.rho_sys, 2)}`;
              cells = [signedN(d.beta), pctN(d.sigma_annual, 1, false), signedN(d.rho_sys, 2)];
            }
            const negative = v !== null && v < 0;
            return (
              <tr key={name} role="row" className={idio ? "idio" : undefined}>
                <NameCell
                  name={name}
                  plain={idio ? specificLabel : (PLAIN[name] ?? "")}
                  keySwatch={<KeySwatch className={key} />}
                  mobile={mobile}
                />
                <td role="cell" className="plot-cell">
                  <BarCell
                    lo={lo}
                    hi={hi}
                    ticks={ticks}
                    value={v}
                    fill={idio ? "hatch" : "factor"}
                    factorSlot={slot}
                    title={title}
                  />
                </td>
                <td role="cell" className="num strong">
                  {pctN(v, 2, negative)}
                </td>
                {stats
                  ? cells.map((c, i) => (
                      <td role="cell" key={i} className="num">
                        {c}
                      </td>
                    ))
                  : null}
              </tr>
            );
          })}
        </tbody>
        <tfoot role="rowgroup">
          <AxisRow ticks={ticks} lo={lo} hi={hi} format={(t) => pctN(t, 0, false)} columns={stats ? 4 : 1} />
        </tfoot>
      </table>
    </Panel>
  );
}
