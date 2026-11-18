import { dateLong } from "../../format";
import type { ReportPanelProps } from "./types";
import "./lead.css";

/** "18 Nov 2026, 09:30 UTC" from an ISO timestamp, or null when it does not parse. */
function stamp(iso: string): string | null {
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return null;
  const text = t.toISOString();
  return `${dateLong(text.slice(0, 10))}, ${text.slice(11, 16)} UTC`;
}

export function Colophon({ report }: ReportPanelProps) {
  const generated = stamp(report.generated_at);
  return (
    <footer className="colophon" id="colophon">
      <p>
        factordesk report, schema v{report.schema_version}
        {generated ? `, generated ${generated}` : ""}. Descriptive statistics on past data; nothing here is a forecast or
        advice.
      </p>
    </footer>
  );
}
