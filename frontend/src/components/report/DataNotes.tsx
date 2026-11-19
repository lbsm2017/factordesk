import { lazy, Suspense, useState } from "react";
import type { FactorReport } from "../../api/types";
import { isMonthly } from "../../report/subject";
import { warningText } from "../../text/plain";
import { noticeItems, plural } from "./leadHelpers";

/** The raw messages and the gate evidence load as their own chunk, only when Details is opened. */
const NoteDetails = lazy(() => import("./NoteDetails").then((m) => ({ default: m.NoteDetails })));

const GLYPH_WARN = (
  <svg className="icon" viewBox="0 0 20 20" aria-hidden="true">
    <path d="M10 2.8 18 16.8H2z" />
    <path d="M10 8v4M10 14.4v.3" />
  </svg>
);

/** Plain summary of the first two distinct warnings, with a count of the rest (month wording when `monthly`). */
export function summaryOf(items: { code: string; message: string }[], monthly = false): string {
  const plain = [...new Set(items.map((item) => warningText(item, monthly)))];
  const summary = plain.slice(0, 2).join(" ");
  return plain.length > 2 ? `${summary} ${plain.length - 2} more are listed under Details.` : summary;
}

/**
 * The data notes line of the Summary: warning glyph, the count, the plain summaries, and a Details
 * link that opens the raw messages. Carries the `#notice` anchor of the header's warnings link.
 */
export function DataNotes({ report }: { report: FactorReport }) {
  const [open, setOpen] = useState(false);
  const items = noticeItems(report);
  if (items.length === 0) return null;
  return (
    <div className="notes-block" id="notice">
      <p className="notes-line" role="note">
        {GLYPH_WARN}
        <span>
          <b>{plural(items.length, "data note", "data notes")}:</b> {summaryOf(items, isMonthly(report))}{" "}
          <button type="button" className="notes-link" aria-expanded={open} aria-controls="notice-details" onClick={() => setOpen(!open)}>
            Details
          </button>
        </span>
      </p>
      <div id="notice-details" className="notes-details" hidden={!open}>
        {open ? (
          <Suspense fallback={null}>
            <NoteDetails report={report} items={items} />
          </Suspense>
        ) : null}
      </div>
    </div>
  );
}
