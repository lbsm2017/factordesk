import type { ReactNode } from "react";

/** Native disclosure for method detail; prints expanded (report.css). */
export function HowComputed({ children }: { children: ReactNode }) {
  return (
    <details className="how">
      <summary>How this is computed</summary>
      <p>{children}</p>
    </details>
  );
}
