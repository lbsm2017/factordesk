import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const STYLES = resolve(import.meta.dirname, "..", "..", "styles");
const tokens = readFileSync(join(STYLES, "tokens.css"), "utf8");
const controls = readFileSync(join(STYLES, "controls.css"), "utf8");

/** Body of the first rule whose selector text contains `selector` (braces balanced). */
function ruleBody(source: string, selector: string): string {
  const at = source.indexOf(selector);
  if (at < 0) throw new Error(`selector not found: ${selector}`);
  const open = source.indexOf("{", at);
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === "{") depth++;
    if (source[i] === "}" && --depth === 0) return source.slice(open + 1, i);
  }
  throw new Error("unbalanced braces");
}

/** A colour token as #rrggbb; `blocks` are searched in order, and var(--x) is followed. */
function hex(name: string, ...blocks: string[]): string {
  for (const block of blocks) {
    const m = new RegExp(String.raw`${name}\s*:\s*([^;]+);`).exec(block);
    if (!m) continue;
    const value = (m[1] as string).trim();
    const ref = /^var\((--[a-z0-9-]+)\)$/.exec(value);
    return ref ? hex(ref[1] as string, ...blocks) : value;
  }
  throw new Error(`${name} not found`);
}

function luminance(color: string): number {
  const channels = [1, 3, 5].map((i) => {
    const c = Number.parseInt(color.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * (channels[0] as number) + 0.7152 * (channels[1] as number) + 0.0722 * (channels[2] as number);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

describe("control boundaries on the rail and on light surfaces (WCAG 1.4.11)", () => {
  const root = ruleBody(tokens, ":root {");
  const t = (name: string) => hex(name, root);

  it("draws rail fields and the range track with edges at least 3:1 on the navy, in light and dark", () => {
    const field = ruleBody(controls, '.controls input[type="text"], .controls input[type="date"]');
    expect(field).toMatch(/border:\s*1px solid var\(--rail-field-line\)/);
    expect(ruleBody(controls, ".seg-range {")).toMatch(/border:\s*1px solid var\(--rail-track\)/);
    const dark = ruleBody(tokens, ':root[data-theme="dark"]');
    for (const [theme, block] of [["light", root], ["dark", dark]] as const) {
      const v = (name: string) => hex(name, block);
      expect(contrast(v("--rail-field-line"), v("--rail")), `${theme} field edge`).toBeGreaterThanOrEqual(3);
      expect(contrast(v("--rail-track"), v("--rail")), `${theme} range track`).toBeGreaterThanOrEqual(3);
    }
  });

  it("marks the chosen preset in cyan with navy text, and cyan only appears on the rail", () => {
    const checked = ruleBody(controls, ".seg-opt input:checked + span");
    expect(checked).toMatch(/background:\s*var\(--rail-cyan\)/);
    expect(checked).toMatch(/color:\s*var\(--rail\)/);
    expect(contrast(t("--rail"), t("--rail-cyan"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(t("--rail-2"), t("--rail"))).toBeGreaterThanOrEqual(4.5);
  });

  it("uses --control-line, at least 3:1 on white, for controls on light surfaces", () => {
    expect(contrast(t("--control-line"), t("--surface"))).toBeGreaterThanOrEqual(3);
    expect(ruleBody(controls, ".landing button.chip")).toMatch(/border-color:\s*var\(--control-line\)/);
    expect(ruleBody(controls, ".ctl-list {")).toMatch(/border:\s*1px solid var\(--control-line\)/);
  });

  it("keeps --line, the panel hairline, below 3:1 (it is decoration, never a control boundary)", () => {
    expect(contrast(t("--line"), t("--surface"))).toBeLessThan(3);
  });
});

describe("analysed-range bar on the rail", () => {
  const t = (name: string) => hex(name, ruleBody(tokens, ":root {"));

  it("draws the three parts from tokens: muted before, cyan analysed, hatched after", () => {
    expect(ruleBody(controls, ".cov-seg.before")).toMatch(/background:\s*var\(--rail-track\)/);
    expect(ruleBody(controls, ".cov-seg.analysed")).toMatch(/background:\s*var\(--rail-cyan\)/);
    const after = ruleBody(controls, ".cov-seg.after");
    expect(after).toMatch(/repeating-linear-gradient\(.*var\(--rail-track\)/);
    expect(after).not.toMatch(/#[0-9a-fA-F]{3,8}b/);
  });

  it("keeps every mark at least 3:1 against the rail (WCAG 1.4.11)", () => {
    expect(contrast(t("--rail-track"), t("--rail"))).toBeGreaterThanOrEqual(3);
    expect(contrast(t("--rail-cyan"), t("--rail"))).toBeGreaterThanOrEqual(3);
  });
});
