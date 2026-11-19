/** Date rules (design B): "8 Aug 2024" from a fixed month table, so there is no locale variance. */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] as const;

export interface IsoParts {
  year: number;
  month: number;
  day: number;
}

/** Parse a strict ISO "YYYY-MM-DD" date; null when the text is not a real calendar date. */
export function parseIsoDate(text: string): IsoParts | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (!m) return null;
  const year = Number(m[1]);
  const month = Number(m[2]);
  const day = Number(m[3]);
  const probe = new Date(Date.UTC(year, month - 1, day));
  if (probe.getUTCFullYear() !== year || probe.getUTCMonth() !== month - 1 || probe.getUTCDate() !== day) {
    return null;
  }
  return { year, month, day };
}

export function isIsoDate(text: string): boolean {
  return parseIsoDate(text) !== null;
}

function parts(text: string): IsoParts {
  const p = parseIsoDate(text);
  if (!p) throw new RangeError(`Not an ISO date: ${text}`);
  return p;
}

/** "8 Aug 2024" */
export function dateLong(text: string): string {
  const { year, month, day } = parts(text);
  return `${day} ${MONTHS[month - 1]} ${year}`;
}

/** "Aug 2024" */
export function dateShort(text: string): string {
  const { year, month } = parts(text);
  return `${MONTHS[month - 1]} ${year}`;
}
