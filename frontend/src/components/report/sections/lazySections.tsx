import { lazy, Suspense } from "react";
import { PanelBoundary } from "../PanelBoundary";
import type { ReportPanelProps } from "../types";

/**
 * The Kalman and shrunk-beta panels load as their own chunks (dashboard spec DV7): they are large
 * and only reports with their section need them. Each renders nothing while its section is null;
 * while its chunk loads, an empty frame with the panel's id and a fixed height holds the place. A
 * chunk that fails to load leaves a notice in the panel's place and the rest of the report on screen.
 */
const Kalman = lazy(() => import("./KalmanPanel").then((m) => ({ default: m.KalmanPanel })));
const Shrunk = lazy(() => import("./ShrunkBetasPanel").then((m) => ({ default: m.ShrunkBetasPanel })));

function Holder({ id }: { id: string }) {
  return <section className="panel sk-lazy" id={id} aria-busy="true" />;
}

export function LazyKalmanPanel({ report }: ReportPanelProps) {
  if (report.kalman_betas === null) return null;
  return (
    <PanelBoundary id="kalman" title="Kalman-filter betas" question="">
      <Suspense fallback={<Holder id="kalman" />}>
        <Kalman report={report} />
      </Suspense>
    </PanelBoundary>
  );
}

export function LazyShrunkBetasPanel({ report }: ReportPanelProps) {
  if (report.shrunk_betas === null) return null;
  return (
    <PanelBoundary id="shrunk" title="Pulled toward typical" question="">
      <Suspense fallback={<Holder id="shrunk" />}>
        <Shrunk report={report} />
      </Suspense>
    </PanelBoundary>
  );
}
