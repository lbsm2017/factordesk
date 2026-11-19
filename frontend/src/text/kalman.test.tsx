import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport, KalmanBetaSeries } from "../api/types";
import { KalmanPanel } from "../components/report/sections/KalmanPanel";
import { cloneReport } from "../test/fixture";
import { withSection } from "../test/sectionFixtures";
import text from "./kalman.json";

/** The wording source of both Kalman panels is the backend file; this folder holds a copy. */
/** Vitest runs from `frontend/`. */
const SOURCE = resolve(process.cwd(), "../backend/factordesk/report/kalman_text.json");
const COPY = resolve(process.cwd(), "src/text/kalman.json");

function flat(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(flat);
  if (value && typeof value === "object") return Object.values(value).flatMap(flat);
  throw new Error(`unexpected JSON value ${String(value)}`);
}

function withKalman(edit?: (s: KalmanBetaSeries) => void): FactorReport {
  const report = withSection(cloneReport(), "kalman_betas");
  if (edit && report.kalman_betas) edit(report.kalman_betas);
  return report;
}

const squash = (s: string) => s.replace(/\s+/g, " ");

describe("Kalman panel wording", () => {
  it("is the same file as the backend source (run `npm run sync:kalman-text` after a change)", () => {
    expect(readFileSync(COPY, "utf8").replace(/\r\n/g, "\n")).toBe(readFileSync(SOURCE, "utf8").replace(/\r\n/g, "\n"));
    expect(text).toEqual(JSON.parse(readFileSync(SOURCE, "utf8")));
  });

  it("is plain text with known placeholders only", () => {
    for (const s of flat(text)) {
      expect(s).toBe(s.trim());
      expect(s).not.toMatch(/<|\s\s/);
      for (const m of s.matchAll(/\{(\w+)\}/g)) expect(["first", "last", "rows"]).toContain(m[1]);
    }
  });

  it("prints every chosen text on a drawn panel with limits and a warning", () => {
    const report = withKalman((s) => {
      s.vintages[1]!.lam_at_bound = "upper";
      s.vintages[1]!.lam = 0.01;
      s.vintages[2]!.lam_at_bound = "zero";
      s.vintages[2]!.lam = 0;
      s.vintages[2]!.w_eq = null;
      s.warnings = ["kalman_lambda_at_upper_bound"];
    });
    const { container } = render(<KalmanPanel report={report} />);
    const seen = squash(container.textContent ?? "") + " " + container.innerHTML;
    const must = [
      "Tracked day by day",
      text.question,
      text.reading,
      ...text.legend,
      ...Object.values(text.beta_heads),
      text.vintage_title,
      ...text.vintage_heads,
      text.window_none,
      ...Object.values(text.bound),
      ...Object.values(text.fold),
      ...Object.values(text.warnings),
    ];
    for (const s of must) expect(seen, s).toContain(s);
    expect(container.querySelector("th[title]")?.getAttribute("title")).toBe(text.sd_title);
    expect(container.querySelector("caption")?.textContent).toContain(text.table_caption.split("{last}")[0]);
    expect(container.querySelector(".foot > p")?.textContent).toContain("The chart starts at 12 Sep 2023, the first date with 504 trading days");
  });

  it("prints the chosen next steps and the warm-up wording in the empty states", () => {
    const failed = render(
      <KalmanPanel
        report={withKalman((s) => {
          s.status = "failed";
          s.reason = "r";
        })}
      />,
    );
    expect(failed.container.querySelector(".empty-do")?.textContent).toBe(text.empty.failed);
    const short = render(
      <KalmanPanel
        report={withKalman((s) => {
          s.status = "insufficient_data";
          s.reason = "r";
        })}
      />,
    );
    expect(short.container.querySelector(".empty-do")?.textContent).toBe(text.empty.insufficient_data.replace("{rows}", "504"));
    const warm = render(
      <KalmanPanel
        report={withKalman((s) => {
          for (const name of Object.keys(s.betas)) {
            s.betas[name] = s.betas[name]!.map(() => null);
            s.band_low[name] = s.band_low[name]!.map(() => null);
            s.band_high[name] = s.band_high[name]!.map(() => null);
          }
        })}
      />,
    );
    expect(warm.container.querySelector(".empty-what")?.textContent).toBe(text.empty.warm_up_reason);
    expect(warm.container.querySelector(".empty-do")?.textContent).toBe(text.empty.warm_up_step);
  });
});
