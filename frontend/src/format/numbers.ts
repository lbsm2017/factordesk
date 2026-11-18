/** Number rules of the report (design B): true minus U+2212, "+" on signed values, zero unsigned. */

export const MINUS = "−";

function grouped(abs: number, digits: number): string {
  const [int = "0", frac] = abs.toFixed(digits).split(".");
  const withCommas = int.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return frac === undefined ? withCommas : `${withCommas}.${frac}`;
}

function isZero(text: string): boolean {
  return Number(text.replace(/,/g, "")) === 0;
}

/** Signed number: "+0.998", "−0.141", and "0.000" for zero (also for values that round to zero). */
export function signed(x: number, digits = 3): string {
  const s = grouped(Math.abs(x), digits);
  if (isZero(s)) return s;
  return (x > 0 ? "+" : MINUS) + s;
}

/** Number with a minus sign only when negative and not rounding to zero. */
export function num(x: number, digits = 3): string {
  const s = grouped(Math.abs(x), digits);
  return x < 0 && !isZero(s) ? MINUS + s : s;
}

/** Percent from a decimal: pct(0.0081) is "+0.81%"; pass withSign = false to drop the plus. */
export function pct(x: number, digits = 2, withSign = true): string {
  return (withSign ? signed : num)(x * 100, digits) + "%";
}

/** t or z statistic: no decimals from 100 up, one decimal below. */
export function tstat(z: number): string {
  return Math.abs(z) >= 100 ? num(z, 0) : num(z, 1);
}

/** p-value: "<0.001" below 0.001, else three decimals. */
export function pval(p: number): string {
  return p < 0.001 ? "<0.001" : p.toFixed(3);
}
