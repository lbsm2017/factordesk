import type { FactorDataStatus, FactorReport, RangeOptions, TickerSuggestion } from "../../api/types";
import type { UrlState } from "../../state/url";
import { Panel } from "../report/Panel";

export interface ControlsStripProps {
  /** Committed URL state. */
  state: UrlState;
  /** Recent tickers, newest first (at most 8). */
  recent: string[];
  /** Server suggestions for the text being typed. */
  suggestions: TickerSuggestion[];
  /** Availability of each preset for the current ticker. */
  ranges: RangeOptions | undefined;
  factorStatus: FactorDataStatus | undefined;
  /** The report on screen, for the analysed-range label. */
  report: FactorReport | undefined;
  /** A request is running (the strip stays usable). */
  busy: boolean;
  /** A factor refresh is running. */
  refreshing: boolean;
  /** Result of the last factor refresh, announced politely. */
  refreshMessage: string | null;
  /** Text typed into the search field (debounced by App before it becomes a query). */
  onQueryChange: (query: string) => void;
  /** Commit a change: submit a ticker, pick a chip, complete a date. App pushes a history entry. */
  onCommit: (patch: Partial<UrlState>) => void;
  onRefreshFactors: () => void;
}

/** STUB (T4): fill in this file only. Props are fixed by T3. */
export function ControlsStrip(_props: ControlsStripProps) {
  return <Panel id="controls" title="Controls" />;
}
