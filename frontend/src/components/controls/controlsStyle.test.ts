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

describe("control boundaries (WCAG 1.4.11)", () => {
  const lightBlock = ruleBody(tokens, ":root {");
  const darkBlock = ruleBody(ruleBody(tokens, "@media (prefers-color-scheme: dark)"), ":root:where");
  const light = (name: string) => hex(name, lightBlock);
  const dark = (name: string) => hex(name, darkBlock, lightBlock);

  it("--axis is at least 3:1 against --surface in light and dark", () => {
    expect(contrast(light("--axis"), light("--surface"))).toBeGreaterThanOrEqual(3);
    expect(contrast(dark("--axis"), dark("--surface"))).toBeGreaterThanOrEqual(3);
  });

  it("--border, the old control boundary, stays below 3:1 (so the check above is meaningful)", () => {
    expect(contrast(light("--border"), light("--surface"))).toBeLessThan(3);
    expect(contrast(dark("--border"), dark("--surface"))).toBeLessThan(3);
  });

  it.each([
    ["text and date inputs", '.controls .ctl-row input[type="text"]'],
    ["range chips", ".controls .chip-opt span"],
    ["recent-ticker buttons", ".landing button.chip"],
  ])("%s draw their boundary with --axis", (_name, selector) => {
    expect(ruleBody(controls, selector)).toMatch(/border-color:\s*var\(--axis\)/);
  });
});
