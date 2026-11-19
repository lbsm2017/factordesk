/**
 * Outcome lines of the Drawdown and World beta panels (dashboard v2 spec DV4.9). They sit apart from
 * `outcome.ts` because only the lazy panel chunks use them.
 */
import type { FactorReport, PerformanceSection } from "../api/types";
import { dateLong, num, pct } from "../format";
import { finite, isoMs } from "../report/derive";
import { compareFits } from "../components/report/sections/worldBetaModel";
import { plural } from "./outcome";

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const COMPARED = { higher: "higher than", lower: "lower than", about_the_same: "about the same as" } as const;

function pct1(x: number): string {
  return pct(Math.abs(x), 1, false);
}

/** "March 2008" from an ISO date. */
function monthYear(iso: string): string {
  const month = MONTHS[Number(iso.slice(5, 7)) - 1];
  return month ? `${month} ${iso.slice(0, 4)}` : dateLong(iso);
}

/** Drawdown: growth a year, the largest fall and its recovery. Null without the returns or the drawdown. */
export function drawdownOutcome(report: FactorReport, section: PerformanceSection): string | null {
  const cagr = finite(section.returns?.cagr);
  const dd = section.drawdown;
  if (cagr === null || dd === null) return null;
  const end = section.periods?.end ?? section.sample.end;
  const move = pct1(cagr) === "0.0%" ? "was flat" : `${cagr > 0 ? "grew" : "shrank"} ${pct1(cagr)} a year`;
  const t = report.ticker;
  if (dd.peak_date === null || dd.trough_date === null) {
    return `${t} ${move} over the analysed range; its price never fell below an earlier high.`;
  }
  const fall = `its largest fall was ${pct1(dd.max_drawdown)}, from ${dateLong(dd.peak_date)} to ${dateLong(dd.trough_date)}`;
  const back =
    dd.recovery_date !== null
      ? `and it was back at the peak by ${dateLong(dd.recovery_date)}`
      : `and it had not recovered${end ? ` by ${dateLong(end)}` : ""}`;
  return `${t} ${move} over the analysed range; ${fall}, ${back}.`;
}

/** World beta: the beta against ACWI and the US market beta on the same days, with the span note. */
export function worldBetaOutcome(report: FactorReport): string | null {
  const s = report.world_beta;
  if (!s || s.status !== "ok" || !s.world || !s.us_market || !s.sample.start || !s.sample.end) return null;
  const phrase = COMPARED[compareFits(s.world, s.us_market)];
  const days = plural(s.sample.n, "day", "days");
  let text =
    `Against world stocks, ${report.ticker}'s beta was ${num(s.world.beta, 2)} over ${dateLong(s.sample.start)} to ${dateLong(s.sample.end)} ` +
    `(${days}), ${phrase} its beta against the US market on the same days (${num(s.us_market.beta, 2)}).`;
  if (s.sample.start !== report.data.actual_start) {
    // The first shared return falls on the fund's second price date, so "starts there" allows a week.
    const first = s.acwi_first_date;
    const gapDays = first === null ? Infinity : (isoMs(s.sample.start) - isoMs(first)) / 86_400_000;
    const reason =
      first !== null && gapDays >= 0 && gapDays <= 7
        ? `the fund's history starts in ${monthYear(first)}`
        : `the two price histories overlap only from ${dateLong(s.sample.start)}`;
    text += ` This covers a shorter span than the five-factor model, because ${reason}.`;
  }
  return text;
}
