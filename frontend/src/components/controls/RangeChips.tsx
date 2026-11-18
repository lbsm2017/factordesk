import type { RangeOption } from "../../api/types";
import type { Preset } from "../../state/url";
import { Panel } from "../report/Panel";

export interface RangeChipsProps {
  /** From the ranges endpoint; undefined while loading. Render only the presets in PRESETS. */
  options: RangeOption[] | undefined;
  /** Selected preset; null when custom dates are used. */
  selected: Preset | null;
  onSelect: (preset: Preset) => void;
}

/** STUB (T4): fill in this file only. Props are fixed by T3. */
export function RangeChips(_props: RangeChipsProps) {
  return <Panel id="range-chips" title="Date range" />;
}
