import type { TickerSuggestion } from "../../api/types";
import { Panel } from "../report/Panel";

export interface TickerSearchProps {
  /** Ticker in the URL, shown in the field after a submit. */
  value: string;
  recent: string[];
  suggestions: TickerSuggestion[];
  /** Inline sentence for a client-side invalid ticker. */
  error: string | null;
  onQueryChange: (query: string) => void;
  /** Enter or a chosen suggestion; the text is not yet upper-cased or validated. */
  onSubmit: (text: string) => void;
}

/** STUB (T4): fill in this file only. Props are fixed by T3. */
export function TickerSearch(_props: TickerSearchProps) {
  return <Panel id="ticker-search" title="Ticker search" />;
}
