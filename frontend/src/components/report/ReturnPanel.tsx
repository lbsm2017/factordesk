/* eslint-disable jsx-a11y/no-redundant-roles, jsx-a11y/no-interactive-element-to-noninteractive-role --
   DB7 asks for explicit table roles: the narrow-screen CSS restyles rows as grids, which can drop table semantics. */
import { returnsOutcome } from "../../text/outcome";
import { PLAIN } from "../../text/plain";
import { describe, factorOrder, finite, labelTexts, niceDomain, sci } from "../../report/derive";
import { pct } from "../../format";
import { BarCell } from "../charts/BarCell";
import { AxisRow, Legend, NameCell, pctN, SigHead, Swatch, TotalSwatch } from "./barParts";
import { Panel } from "./Panel";
import type { ReportPanelProps } from "./types";
import "./signColor.css";

type Kind = "factor" | "alpha" | "resid";

interface Item {
  name: string;
  plain: string;
  value: number | null;
  notSignificant: boolean;
  kind: Kind;
}

/** Axis label: "0%", "+5%", "+2.5%". */
export function returnTick(t: number): string {
  if (!t) return "0%";
  return pct(t, Math.abs(t * 100 - Math.round(t * 100)) < 1e-9 ? 0 : 1);
}

/** Sign colour of a return value (class names of the v4a sign colour); missing and shown-as-zero stay ink. */
export function signClass(x: number | null): string {
  return x === null || pctN(x) === "0.00%" ? "" : x > 0 ? " num-pos" : " num-neg";
}

const EMPTY_ACTION = "Widen the date range and run the report again.";

/** Panel 6: where the return came from. Bars add up to the total; residual is hatched. */
export function ReturnPanel({ report }: ReportPanelProps) {
  const rc = report.return_contribution;
  const reg = report.regression;
  const title = "Return sources";
  const question = "How much of the average yearly return does each factor explain?";

  const tags = new Map(reg.factors.map((f) => [f.name, f.tag]));
  const items: Item[] = [
    ...factorOrder(report).map<Item>((name) => ({
      name,
      plain: PLAIN[name] ?? "",
      value: finite(rc.factors[name]),
      notSignificant: tags.get(name) !== "reliable",
      kind: "factor",
    })),
    {
      name: "Alpha",
      plain: "Unexplained average",
      value: finite(rc.alpha),
      notSignificant: reg.alpha_tag !== "reliable",
      kind: "alpha",
    },
    { name: "Residual", plain: "Zero by construction", value: finite(rc.residual), notSignificant: false, kind: "resid" },
  ];
  const total = finite(rc.total_annualised_mean_excess_return);
  const values = items.flatMap((i) => (i.value === null ? [] : [i.value]));

  if (rc.status !== "ok") {
    return (
      <Panel
        id="returns"
        title={title}
        question={question}
        empty={{ reason: rc.reason ?? "The return attribution could not be computed.", action: EMPTY_ACTION }}
      />
    );
  }
  if (values.length === 0 && total === null) {
    return (
      <Panel
        id="returns"
        title={title}
        question={question}
        empty={{ reason: "Insufficient data: no return attribution available.", action: EMPTY_ACTION }}
      />
    );
  }

  const { lo, hi, ticks } = niceDomain(Math.min(...values, 0, total ?? 0), Math.max(...values, 0, total ?? 0), 3);

  const checks: string[] = [];
  const resid = finite(rc.residual);
  if (resid !== null) checks.push(`Residual ${sci(resid)} (zero by construction).`);
  const ident = finite(rc.identity_residual);
  if (ident !== null) checks.push(`Identity check ${sci(ident)}.`);
  const how = [
    rc.caption,
    `Each factor's share is its full-sample beta times the factor's average return, times ${report.subject?.periods ?? 252}. Arithmetic, not compounded.`,
    ...labelTexts(report, rc.labels),
    checks.join(" "),
  ]
    .filter(Boolean)
    .join(" ");

  const desc = describe(report);

  return (
    <Panel
      id="returns"
      title={title}
      question={question}
      legend={
        <Legend
          items={[
            <>
              <Swatch kind="pos" />
              Adds
            </>,
            <>
              <Swatch kind="neg" />
              Subtracts
            </>,
            <>
              <Swatch kind="pos" faded />
              Faded: not significant
            </>,
            <>
              <Swatch kind="hatch" />
              Residual
            </>,
            <>
              <TotalSwatch />
              Total
            </>,
          ]}
        />
      }
      outcome={returnsOutcome(report)}
      footnote={`${desc} The rows add up exactly to the total.`}
      how={how}
    >
      <table role="table" className="bars cols-2">
        <caption className="vh">
          Return contribution per factor, alpha and residual, percent a year, with the total
        </caption>
        <thead role="rowgroup">
          <tr role="row">
            <th role="columnheader" scope="col">
              Component
            </th>
            <th role="columnheader" scope="col" className="plot-h">
              <span className="vh">Chart</span>
            </th>
            <th role="columnheader" scope="col" className="num">
              % a year
            </th>
            <th role="columnheader" scope="col" className="num">
              <SigHead />
            </th>
          </tr>
        </thead>
        <tbody role="rowgroup">
          {items.map((item) => {
            const id = item.kind === "alpha" ? "ret-alpha" : `ret-${item.name}`;
            const sig = item.kind === "resid" ? "–" : item.notSignificant ? "No" : "Yes";
            return (
              <tr
                key={id}
                id={id}
                role="row"
                className={`${item.notSignificant ? "ns is-noise " : ""}${item.kind}`}
                tabIndex={-1}
              >
                <NameCell name={item.name} plain={item.plain} />
                <td role="cell" className="plot-cell">
                  <BarCell
                    lo={lo}
                    hi={hi}
                    ticks={ticks}
                    value={item.value}
                    fill={item.kind === "resid" ? "hatch" : "sign"}
                    faded={item.notSignificant}
                    title={`${item.name}: ${pctN(item.value)} a year`}
                  />
                </td>
                <td role="cell" className={`num strong${item.kind === "resid" ? "" : signClass(item.value)}`}>
                  {pctN(item.value)}
                </td>
                <td role="cell" className="num sig">
                  {sig}
                </td>
              </tr>
            );
          })}
          <tr role="row" className="total">
            <th role="rowheader" scope="row">
              <span className="fname">Total</span>
              <span className="sub">Mean excess return</span>
            </th>
            <td role="cell" className="plot-cell">
              <BarCell
                lo={lo}
                hi={hi}
                ticks={ticks}
                value={null}
                total={total}
                fill="sign"
                title={`Total: ${pctN(total)} a year`}
              />
            </td>
            <td role="cell" className={`num strong${signClass(total)}`}>
              {pctN(total)}
            </td>
            <td role="cell" className="num" />
          </tr>
        </tbody>
        <tfoot role="rowgroup">
          <AxisRow ticks={ticks} lo={lo} hi={hi} format={returnTick} columns={2} />
        </tfoot>
      </table>
      {rc.memo.length > 0 ? (
        <div className="memo">
          <h3>Not in the sum</h3>
          <ul>
            {rc.memo.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </Panel>
  );
}
