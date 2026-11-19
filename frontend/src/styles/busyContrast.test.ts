import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const tokens = readFileSync(resolve(process.cwd(), "src/styles/tokens.css"), "utf8");
const frame = readFileSync(resolve(process.cwd(), "src/styles/frame.css"), "utf8");

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * (r as number) + 0.7152 * (g as number) + 0.0722 * (b as number);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

/** `--name: #hex` from the part of tokens.css that starts at `marker` (first match after it). */
function token(marker: string, name: string): string {
  const from = tokens.indexOf(marker);
  expect(from, marker).toBeGreaterThanOrEqual(0);
  const m = new RegExp(String.raw`${name}:\s*(#[0-9a-fA-F]{6})`).exec(tokens.slice(from));
  expect(m, `${name} after ${marker}`).not.toBeNull();
  return m?.[1] as string;
}

describe("busy placeholder on the page background (review S4)", () => {
  it("fills with --border, not --grid", () => {
    const rule = /\[aria-busy="true"\] \.ticker[^{]*\{([^}]*)\}/.exec(frame);
    expect(rule?.[1]).toMatch(/background:\s*var\(--border\)/);
  });

  it.each([["--page"], ["--surface"]])("is more visible than --grid against %s", (ground) => {
    const bg = token(":root {", ground);
    const border = contrast(token(":root {", "--line"), bg);
    const grid = contrast(token(":root {", "--grid"), bg);
    expect(border).toBeGreaterThan(grid);
    expect(border).toBeGreaterThanOrEqual(1.2);
  });
});
