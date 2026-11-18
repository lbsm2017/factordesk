import type { MouseEvent } from "react";
import { MINUS, num, pct, signed, tstat } from "../../format";
import { PLAIN } from "../../text/plain";
import { fin } from "./leadHelpers";
import type { ReportPanelProps } from "./types";
import "./lead.css";

/**
 * Scroll to and focus the row a term links to. The native anchor still runs, so the hash is set
 * and the row gets the `:target` wash; focus makes keyboard and screen-reader users land on it.
 */
function focusRow(event: MouseEvent<HTMLAnchorElement>): void {
  const id = event.currentTarget.getAttribute("href")?.slice(1);
  const row = id ? document.getElementById(id) : null;
  if (!row) return;
  if (!row.hasAttribute("tabindex")) row.setAttribute("tabindex", "-1");
  row.focus();
}

function Annotation({ name, significant, z }: { name: string; significant: boolean; z: number | null }) {
  return (
    <span className="ann">
      <span>{name}</span>
      <span>
        {significant ? "significant" : "not significant"}, t {z === null ? "n/a" : tstat(z)}
      </span>
    </span>
  );
}

/** The fitted daily model, typeset in STIX Two (design 2). Omitted when the regression is not ok. */
export function Equation({ report }: ReportPanelProps) {
  const g = report.regression;
  const alpha = fin(g.alpha_annual);
  const betas = g.factors.map((s) => ({ stat: s, beta: fin(s.beta) }));
  if (g.status !== "ok" || alpha === null || betas.length === 0 || betas.some((b) => b.beta === null)) {
    return null;
  }
  const sigma = fin(g.sigma_e_annual);
  const alphaNs = g.alpha_tag !== "reliable";
  const label =
    "Fitted model: daily excess return equals " +
    [`alpha ${pct(alpha)} a year`, ...betas.map(({ stat, beta }) => `${signed(beta as number)} times ${stat.name}`)].join(
      ", ",
    ) +
    ", plus a residual.";

  return (
    <figure className="model" id="equation" aria-label={label}>
      <div className="eq">
        <span className="lhs" aria-hidden="true">
          <var>r</var>
          <span className="op">−</span>
          <var>r</var>
          <sub>f</sub>
          <span className="op eqs">=</span>
        </span>
        <span className="terms">
          <a className={`term${alphaNs ? " ns" : ""}`} href="#ret-alpha" onClick={focusRow}>
            <span className="m">
              {alpha < 0 ? MINUS : ""}
              {num(Math.abs(alpha) * 100, 2)}%
            </span>
            <Annotation name="alpha, a year" significant={!alphaNs} z={fin(g.alpha_z)} />
          </a>
          {betas.map(({ stat, beta }) => {
            const b = beta as number;
            const ns = stat.tag !== "reliable";
            return (
              <a key={stat.name} className={`term${ns ? " ns" : ""}`} href={`#beta-${stat.name}`} onClick={focusRow}>
                <span className="m">
                  <span className="op">{b >= 0 ? "+" : MINUS}</span>
                  {num(Math.abs(b), 3)}
                  <span className="fn">{stat.name}</span>
                </span>
                <Annotation name={(PLAIN[stat.name] ?? stat.name).toLowerCase()} significant={!ns} z={fin(stat.z)} />
              </a>
            );
          })}
          <span className="term eps">
            <span className="m">
              <span className="op">+</span>
              <var>ε</var>
            </span>
            <span className="ann">
              <span>residual</span>
              <span>{sigma === null ? "n/a" : `${pct(sigma, 1, false)} a year`}</span>
            </span>
          </span>
        </span>
      </div>
      <figcaption>
        The fitted daily model, in-sample. Faded terms are not statistically significant. Select a term to see its
        detail.
      </figcaption>
    </figure>
  );
}
