import type { FactorReport } from "../../api/types";
import { Panel } from "../report/Panel";

export interface AnalysedRangeProps {
  /** undefined before the first report. */
  report: FactorReport | undefined;
}

/** STUB (T4): fill in this file only. Props are fixed by T3. aria-live="polite". */
export function AnalysedRange(_props: AnalysedRangeProps) {
  return <Panel id="analysed-range" title="Analysed range" />;
}
