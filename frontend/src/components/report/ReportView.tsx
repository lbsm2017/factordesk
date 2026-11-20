import { useEffect, useState } from "react";
import type { FactorReport } from "../../api/types";
import type { RollingWindowDays } from "../../state/url";
import "../../styles/frame.css";
import { Hatch } from "../charts/Hatch";
import { hiddenPanels } from "../../report/applicability";
import { orderedPanels } from "./panelRegistry";
import type { PanelHostProps } from "./panelRegistry";

export interface ReportViewProps {
  report: FactorReport;
  /** `/api/report/{t}/html?{same range}`, for the Download link in the header; null hides it. */
  downloadHref: string | null;
  /** Rolling window from the URL (`win`); null means the report's primary window. */
  win: RollingWindowDays | null;
  onWinChange: (win: RollingWindowDays) => void;
  /** A new request is running: `aria-busy` on the region. */
  busy?: boolean;
  /** A re-run is on its way: the report stays, dimmed and inert (Sprint 4 mockup 1, frame e). */
  dim?: boolean;
  /** The report has just arrived after a visible run: its panels appear one after another (frame d). */
  reveal?: boolean;
}

/** The reveal lasts about 620 ms; the class stays a little longer so the last panel finishes. */
const REVEAL_MS = 700;

function reducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Panel order, checked once (contract SC4): a repeated name or position fails at load. */
const PANELS_IN_ORDER = orderedPanels();

/**
 * Places every panel in the report's order (design C) from the panel registry (`panelRegistry.ts`,
 * schema v3 contract). Panel tickets never edit this file: add a panel by filling its own file.
 */
export function ReportView({ report, downloadHref, win, onWinChange, busy = false, dim = false, reveal = false }: ReportViewProps) {
  // The reveal is over for the report it ran for after REVEAL_MS; with reduced motion there is none.
  const [revealedFor, setRevealedFor] = useState<FactorReport | null>(null);
  const instant = reveal && reducedMotion();
  const revealing = reveal && !instant && revealedFor !== report;
  useEffect(() => {
    if (!reveal || instant) return;
    const id = window.setTimeout(() => setRevealedFor(report), REVEAL_MS);
    return () => window.clearTimeout(id);
  }, [reveal, instant, report]);
  const primary: RollingWindowDays = report.average_beta.window === 126 ? 126 : 252;
  const host: PanelHostProps = { report, downloadHref, win: win ?? primary, onWinChange };
  const hidden = hiddenPanels(report);
  return (
    <main
      className={`report-region${revealing ? " reveal" : ""}${dim ? " dim" : ""}`}
      aria-busy={busy || revealing}
      inert={dim}
      data-testid="report-region"
    >
      <Hatch />
      {PANELS_IN_ORDER.filter(({ name }) => !hidden.has(name)).map(({ name, Component }) => (
        <Component key={name} {...host} />
      ))}
    </main>
  );
}
