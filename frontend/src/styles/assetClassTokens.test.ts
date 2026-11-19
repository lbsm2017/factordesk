import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(resolve(import.meta.dirname), "tokens.css"), "utf8");

function token(name: string): string {
  const found = new RegExp(`${name}:\\s*(#[0-9A-Fa-f]{6})`).exec(css);
  if (found === null) throw new Error(`${name} not found`);
  return (found[1] as string).toUpperCase();
}

function luminance(color: string): number {
  const channels = [1, 3, 5].map((i) => {
    const c = Number.parseInt(color.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * (channels[0] as number) + 0.7152 * (channels[1] as number) + 0.0722 * (channels[2] as number);
}

const CLASSES = ["equities", "fixed", "alts", "real", "comm", "cash", "other"].map((k) => `--ac-${k}`);
const FACTORS = ["--f1", "--f2", "--f3", "--f4", "--f5", "--f6"];

describe("asset-class palette of the composer", () => {
  it("is its own palette: no colour of it is a factor colour", () => {
    const factors = FACTORS.map(token);
    for (const name of CLASSES) expect(factors, name).not.toContain(token(name));
  });

  it("has seven different colours", () => {
    expect(new Set(CLASSES.map(token)).size).toBe(7);
  });

  it("reaches 3:1 against the white surface (WCAG 1.4.11)", () => {
    for (const name of CLASSES) {
      const lum = luminance(token(name));
      expect((1 + 0.05) / (lum + 0.05), name).toBeGreaterThanOrEqual(3);
    }
  });
});
