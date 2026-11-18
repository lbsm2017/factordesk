import type { RollingWindowDays } from "../../state/url";
import { Panel } from "./Panel";
import type { ReportPanelProps } from "./types";

export interface RollingPanelProps extends ReportPanelProps {
  /** Window shown. ReportView passes `win ?? report.average_beta.window`. */
  win: RollingWindowDays;
  /** Commit a window change (App writes `win` to the URL). */
  onWinChange: (win: RollingWindowDays) => void;
}

/** STUB (T7): fill in this file only. Props are fixed by T3. */
export function RollingPanel(_props: RollingPanelProps) {
  return (
    <Panel
      id="rolling"
      title="Exposure over time"
      question="Have the exposures been stable, or did they drift?"
    />
  );
}
