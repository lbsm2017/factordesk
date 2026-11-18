import { useState } from "react";
import type { FactorDataStatus, FactorReport, RangeOptions, TickerSuggestion } from "../../api/types";
import { checkTicker } from "../../state/url";
import type { Preset, UrlState } from "../../state/url";
import { AnalysedRange } from "./AnalysedRange";
import { CustomRange } from "./CustomRange";
import { FactorDataLine } from "./FactorDataLine";
import { RangeChips } from "./RangeChips";
import { TickerSearch } from "./TickerSearch";

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

const WHY_ID = "ctl-why";

/** The preset the chips show: custom dates clear it, and no range in the URL means Full history. */
export function selectedPreset(state: UrlState): Preset | null {
  if (state.start || state.end) return null;
  return state.range ?? "FULL";
}

/**
 * One framed strip above the header (design I, dashboard spec DB6.3): ticker search and "Factor it",
 * range chips, From and To, the analysed-range label, the factor-data line, and the reason for any
 * disabled chip as visible text.
 */
export function ControlsStrip({
  state,
  recent,
  suggestions,
  ranges,
  factorStatus,
  report,
  busy,
  refreshing,
  refreshMessage,
  onQueryChange,
  onCommit,
  onRefreshFactors,
}: ControlsStripProps) {
  const [tickerError, setTickerError] = useState<string | null>(null);

  const unavailable = ranges?.options.filter((o) => !o.available && o.reason !== null) ?? [];
  const max = ranges?.factors_last_date ?? factorStatus?.last_date ?? null;

  return (
    <section className="controls" aria-label="Report controls">
      <div className="ctl-row">
        <TickerSearch
          value={state.ticker ?? ""}
          recent={recent}
          suggestions={suggestions}
          error={tickerError}
          focusOnMount={state.ticker === null}
          onQueryChange={(query) => {
            setTickerError(null);
            onQueryChange(query);
          }}
          onSubmit={(text) => {
            const checked = checkTicker(text);
            if (!checked.ok) {
              setTickerError(checked.message);
              return;
            }
            setTickerError(null);
            onCommit({ ticker: checked.ticker });
          }}
        />
        <RangeChips
          options={ranges?.options}
          selected={selectedPreset(state)}
          onSelect={(preset) => onCommit({ range: preset, start: null, end: null })}
          {...(unavailable.length > 0 ? { describedBy: WHY_ID } : {})}
        />
        <CustomRange
          start={state.start ?? report?.data.actual_start ?? ""}
          end={state.end ?? report?.data.actual_end ?? ""}
          max={max}
          onCommit={(start, end) => onCommit({ range: null, start, end })}
        />
      </div>
      <AnalysedRange report={report} />
      <FactorDataLine status={factorStatus} refreshing={refreshing} message={refreshMessage} onRefresh={onRefreshFactors} />
      {unavailable.length > 0 ? (
        <div className="ctl-why" id={WHY_ID}>
          {unavailable.map((option) => (
            <p key={option.preset}>{option.reason}</p>
          ))}
        </div>
      ) : null}
      <span className="vh" role="status">
        {busy ? "Loading the report." : ""}
      </span>
    </section>
  );
}
