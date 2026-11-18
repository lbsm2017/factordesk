/* eslint-disable jsx-a11y/no-interactive-element-to-noninteractive-role --
   DB7 asks for explicit table roles: the narrow-screen CSS restyles rows as grids, which can drop table semantics. */
/** Small pieces shared by the return, risk and rolling tables (ports of the static renderer's helpers). */
import type { ReactNode } from "react";
import { MINUS, num, pct, signed } from "../../format";
import { position } from "../charts/BarCell";
import "./barParts.css";

/** "n/a" for a missing value. */
export function signedN(x: number | null | undefined, digits = 3): string {
  return x == null ? "n/a" : signed(x, digits);
}

export function pctN(x: number | null | undefined, digits = 2, withSign = true): string {
  return x == null ? "n/a" : pct(x, digits, withSign);
}

export function numN(x: number | null | undefined, digits = 3): string {
  return x == null ? "n/a" : num(x, digits);
}

export { MINUS };

/** Legend swatch: a bar colour, optionally the faded (not significant) form. */
export function Swatch({ kind, faded = false }: { kind: "pos" | "neg" | "hatch"; faded?: boolean }) {
  return (
    <svg className="sw" aria-hidden="true">
      {faded ? (
        <rect className={`${kind} faded`} x="0.5" y="0.5" width="13" height="9" rx="2" />
      ) : (
        <rect className={kind} width="14" height="10" rx="2" />
      )}
    </svg>
  );
}

/** Legend swatch for the total: a rule with a cap. */
export function TotalSwatch() {
  return (
    <svg className="sw" aria-hidden="true">
      <line className="total-line" x1="0" x2="13" y1="5" y2="5" />
      <line className="total-cap" x1="13" x2="13" y1="0" y2="10" />
    </svg>
  );
}

/** The 8 px key square beside a factor name. */
export function KeySwatch({ className }: { className: string }) {
  return (
    <svg className="key" aria-hidden="true">
      <rect className={className} width="8" height="8" rx="1" />
    </svg>
  );
}

export function Legend({ items }: { items: ReactNode[] }) {
  return (
    <ul className="legend" aria-label="Legend">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

/** Row header: factor code with an optional key square, then the plain name under it. */
export function NameCell({
  name,
  plain,
  keySwatch,
  mobile,
}: {
  name: string;
  plain: string;
  keySwatch?: ReactNode;
  /** A second line shown only under 720 px. */
  mobile?: string;
}) {
  return (
    <th role="rowheader" scope="row">
      <span className="fname">
        {keySwatch}
        {name}
      </span>
      {plain ? <span className="sub">{plain}</span> : null}
      {mobile ? <span className="sub mob">{mobile}</span> : null}
    </th>
  );
}

function edge(x: number): string {
  return x < 3 ? "edge-l" : x > 97 ? "edge-r" : "";
}

/** The tick-label row under a bar table; hidden from assistive technology. */
export function AxisRow({
  ticks,
  lo,
  hi,
  format,
  columns,
}: {
  ticks: readonly number[];
  lo: number;
  hi: number;
  format: (t: number) => string;
  /** Number of number columns after the plot column. */
  columns: number;
}) {
  const zeroAt = Math.max(
    ticks.findIndex((t) => Math.abs(t) < 1e-12),
    0,
  );
  return (
    <tr className="axis-row" role="row" aria-hidden="true">
      <td role="cell" />
      <td role="cell" className="axis">
        {ticks.map((t, k) => {
          const x = position(t, lo, hi);
          const alt = (k - zeroAt) % 2 !== 0 && ticks.length > 5 ? " alt" : "";
          return (
            <span key={t} className={`${edge(x)}${alt}`.trim()} style={{ left: `${x}%` }}>
              {format(t)}
            </span>
          );
        })}
      </td>
      <td role="cell" colSpan={columns} />
    </tr>
  );
}

/**
 * Content of the "Significant" column header. Under 720 px the full word is visually hidden
 * (barParts.css) and "Sig." shows, so the header keeps an accessible name at every width.
 */
export function SigHead() {
  return (
    <>
      <span className="long">Significant</span>
      <span className="short" aria-hidden="true">
        Sig.
      </span>
    </>
  );
}
