import { Panel } from "../report/Panel";

export interface CustomRangeProps {
  /** ISO dates, or "" when empty. Chip choices fill these with the analysed dates. */
  start: string;
  end: string;
  /** Last factor date (the `max` of both date fields), or null while unknown. */
  max: string | null;
  /** Called when a complete, valid pair is entered. */
  onCommit: (start: string, end: string) => void;
}

/** STUB (T4): fill in this file only. Props are fixed by T3. */
export function CustomRange(_props: CustomRangeProps) {
  return <Panel id="custom-range" title="Custom range" />;
}
