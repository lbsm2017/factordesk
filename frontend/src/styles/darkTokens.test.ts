import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(resolve(import.meta.dirname), "tokens.css"), "utf8");

/** The text between the braces of the first rule that starts with `selector`. */
function body(selector: string): string {
  const start = css.indexOf(selector);
  if (start < 0) throw new Error(`${selector} not found`);
  const open = css.indexOf("{", start);
  const close = css.indexOf("}", open);
  return css.slice(open + 1, close);
}

function declarations(text: string): Map<string, string> {
  const out = new Map<string, string>();
  for (const m of text.replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    out.set(m[1] as string, (m[2] as string).trim());
  }
  return out;
}

const light = declarations(body(":root {"));
const dark = declarations(body(':root[data-theme="dark"]'));
const system = declarations(body(":root:not([data-theme])"));

const isColour = (value: string): boolean => /^(#[0-9a-fA-F]{6}|rgba?\()/.test(value);
const colourTokens = [...light].filter(([, value]) => isColour(value)).map(([name]) => name);

function rgb(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16) / 255) as [number, number, number];
}

function luminance(hex: string): number {
  const [r, g, b] = rgb(hex).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

const d = (name: string): string => {
  const value = dark.get(name);
  if (value === undefined) throw new Error(`${name} missing in dark`);
  return value;
};

describe("dark token set", () => {
  it("has a dark value for every colour token of :root, and nothing more", () => {
    expect(colourTokens.length).toBeGreaterThan(40);
    for (const name of colourTokens) expect(dark.has(name), name).toBe(true);
    for (const name of dark.keys()) if (name !== "color-scheme") expect(colourTokens, name).toContain(name);
  });

  it("is the same set under the data-theme choice and under the system setting", () => {
    expect([...system]).toEqual([...dark]);
  });

  it("declares color-scheme dark in both dark blocks", () => {
    expect(body(':root[data-theme="dark"]')).toMatch(/color-scheme:\s*dark/);
    expect(body(":root:not([data-theme])")).toMatch(/color-scheme:\s*dark/);
  });

  it("applies only on screen, so print stays light", () => {
    expect(css).toMatch(/@media screen \{\s*:root\[data-theme="dark"\]/);
    expect(css).toMatch(/@media screen and \(prefers-color-scheme: dark\) \{\s*:root:not\(\[data-theme\]\)/);
  });
});

describe("dark contrast (WCAG 2.2 AA)", () => {
  const grounds = ["--page", "--surface", "--soft", "--sunk"];
  const text = ["--ink", "--ink-2", "--ink-3", "--accent", "--pos", "--neg", "--caution"];

  it.each(text)("text %s reaches 4.5:1 on every surface", (name) => {
    for (const ground of grounds) expect(contrast(d(name), d(ground)), `${name} on ${ground}`).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps sign, caution and ink text readable on their tinted fills", () => {
    expect(contrast(d("--neg"), d("--neg-50"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(d("--caution"), d("--caution-50"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(d("--ink"), d("--neg-50"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(d("--accent"), d("--accent-50"))).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps the label of a primary button readable", () => {
    expect(contrast(d("--on-accent"), d("--accent"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(d("--on-accent"), d("--accent-hover"))).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps text on the rail and in its fields readable", () => {
    for (const name of ["--rail-text", "--rail-2", "--rail-cyan"]) {
      expect(contrast(d(name), d("--rail")), name).toBeGreaterThanOrEqual(4.5);
    }
    expect(contrast(d("--rail-text"), d("--rail-hover"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(d("--rail-2"), d("--rail-hover"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(d("--rail-field-text"), d("--rail-field"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(d("--rail"), d("--rail-cyan"))).toBeGreaterThanOrEqual(4.5);
  });

  const marks = ["--f1", "--f2", "--f3", "--f4", "--f5", "--f6", "--ac-equities", "--ac-fixed", "--ac-alts", "--ac-real", "--ac-comm", "--ac-cash", "--ac-other", "--pos", "--neg", "--axis", "--control-line"];

  it.each(marks)("chart mark or control %s reaches 3:1 on the surface and the page", (name) => {
    for (const ground of ["--surface", "--page"]) expect(contrast(d(name), d(ground)), `${name} on ${ground}`).toBeGreaterThanOrEqual(3);
  });

  it("draws the rail track and the field edge at 3:1 against the rail", () => {
    expect(contrast(d("--rail-track"), d("--rail"))).toBeGreaterThanOrEqual(3);
    expect(contrast(d("--rail-field-line"), d("--rail"))).toBeGreaterThanOrEqual(3);
  });

  it("keeps the dark rail distinct from the page", () => {
    expect(d("--rail")).not.toBe(d("--page"));
    expect(luminance(d("--rail"))).toBeLessThan(luminance(d("--page")));
  });
});
