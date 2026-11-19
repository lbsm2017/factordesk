import type { TailRiskSection } from "../../../api/types";
import { count, pct } from "../../../format";

export type TailFigure = NonNullable<TailRiskSection["figures"]>[number];
export type TailMethod = TailFigure["method"];

export const METHODS: readonly { key: TailMethod; label: string }[] = [
  { key: "historical", label: "Historical" },
  { key: "gaussian", label: "Gaussian" },
  { key: "cornish_fisher", label: "Cornish-Fisher" },
];

export const APPROXIMATE = "approximate (tends to be narrow)";
export const INDICATIVE = "indicative";
export const CAPTION =
  "Losses are shown as positive numbers. Results are at the series' own frequency, with no scaling to other horizons.";

/** One table row: a measure at a confidence level. */
export interface TailRow {
  key: string;
  label: string;
  cells: Record<TailMethod, TailFigure | undefined>;
}

/** "VaR 99%", "CVaR 97.5%". */
export function rowLabel(measure: TailFigure["measure"], level: number): string {
  const percent = Number((level * 100).toFixed(1));
  return `${measure === "var" ? "VaR" : "CVaR"} ${percent}%`;
}

/** The figures grouped by measure and level, in the order the backend sends them. */
export function rowsOf(figures: readonly TailFigure[]): TailRow[] {
  const rows: TailRow[] = [];
  for (const f of figures) {
    const key = `${f.measure}-${f.level}`;
    let row = rows.find((r) => r.key === key);
    if (row === undefined) {
      row = {
        key,
        label: rowLabel(f.measure, f.level),
        cells: { historical: undefined, gaussian: undefined, cornish_fisher: undefined },
      };
      rows.push(row);
    }
    row.cells[f.method] = f;
  }
  return rows;
}

/** "90%" from the band level 0.9. */
export function bandName(level: number): string {
  return `${Number((level * 100).toFixed(1))}%`;
}

/** "720 days", "1 day", "60 months". */
export function basedOn(n: number, monthly: boolean): string {
  const [one, many] = monthly ? ["month", "months"] : ["day", "days"];
  return `${count(n)} ${n === 1 ? one : many}`;
}

/** A loss as a positive percentage ("2.65%"). */
export function loss(x: number): string {
  return pct(x, 2, false);
}
