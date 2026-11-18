/**
 * Page shell (T3). T4 replaces the body with URL state, the controls strip and the data flow.
 * The 1216 px column is the `.report` class (design C).
 */
import { useEffect, useState } from "react";
import type { FactorReport } from "./api/types";
import { ReportView } from "./components/report/ReportView";
import type { RollingWindowDays } from "./state/url";

/** Development only: `/?demo=1` renders the mock report so the stubs can be seen. Removed from the build. */
function useDemoReport(): FactorReport | null {
  const [report, setReport] = useState<FactorReport | null>(null);
  useEffect(() => {
    if (!import.meta.env.DEV || new URLSearchParams(window.location.search).get("demo") !== "1") return;
    void import("./test/fixture").then((m) => setReport(m.mockReport));
  }, []);
  return report;
}

export function App() {
  const demo = useDemoReport();
  const [win, setWin] = useState<RollingWindowDays | null>(null);
  return (
    <div className="report">
      {demo ? (
        <ReportView report={demo} downloadHref="#" win={win} onWinChange={setWin} />
      ) : (
        <main>
          <h1>
            <span className="ticker">factordesk</span>
          </h1>
          <p className="coverage">Type a ticker and press Factor it, for example SPY.</p>
        </main>
      )}
    </div>
  );
}
