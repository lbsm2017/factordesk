import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { CHART_FONT_PX } from "../components/charts/chartTokens";

/** Design rev 3: no text under 14 px anywhere, chart text included. */
const MIN_PX = 14;
const SRC = resolve(import.meta.dirname, "..");

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path, out);
    else out.push(path);
  }
  return out;
}

const files = walk(SRC).filter((f) => !/\.test\.tsx?$/.test(f) && !f.includes(join("src", "api", "")));
const cssFiles = files.filter((f) => f.endsWith(".css"));
const codeFiles = files.filter((f) => /\.tsx?$/.test(f));

const tokens = new Map<string, number>();
for (const f of cssFiles) {
  for (const m of readFileSync(f, "utf8").matchAll(/(--fs-[a-z0-9-]+)\s*:\s*([\d.]+)px/g)) {
    tokens.set(`${m[1]}@${relative(SRC, f)}@${m.index}`, Number(m[2]));
  }
}

function px(value: string, vars: Map<string, number>): number | null {
  const v = value.trim();
  const direct = /^([\d.]+)px$/.exec(v);
  if (direct) return Number(direct[1]);
  const rem = /^([\d.]+)r?em$/.exec(v);
  if (rem) return Number(rem[1]) * 16;
  const ref = /^var\((--fs-[a-z0-9-]+)\)$/.exec(v);
  if (ref) return vars.get(ref[1] as string) ?? null;
  return null;
}

/** Smallest value of each --fs-* token over every declaration (the base one and the media overrides). */
const smallest = new Map<string, number>();
for (const [key, value] of tokens) {
  const name = key.split("@")[0] as string;
  smallest.set(name, Math.min(smallest.get(name) ?? Infinity, value));
}
// Aliases such as --fs-1: var(--fs-cap)
for (const f of cssFiles) {
  for (const m of readFileSync(f, "utf8").matchAll(/(--fs-[a-z0-9-]+)\s*:\s*var\((--fs-[a-z0-9-]+)\)/g)) {
    const target = smallest.get(m[2] as string);
    if (target !== undefined) smallest.set(m[1] as string, target);
  }
}

describe("no text under 14 px", () => {
  it("keeps every --fs-* token at 14 px or more", () => {
    expect(smallest.size).toBeGreaterThan(5);
    for (const [name, value] of smallest) expect(value, name).toBeGreaterThanOrEqual(MIN_PX);
  });

  it("sets no CSS font-size under 14 px, in any unit or through any token", () => {
    const bad: string[] = [];
    for (const f of cssFiles) {
      const text = readFileSync(f, "utf8");
      for (const m of text.matchAll(/font-size\s*:\s*([^;}]+)/g)) {
        const value = (m[1] as string).trim();
        if (/^(inherit|initial|unset|inherit !important)$/.test(value)) continue;
        const size = px(value, smallest);
        if (size === null || size < MIN_PX) bad.push(`${relative(SRC, f)}: font-size ${value}`);
      }
      // The font shorthand: "font: 11px/1.2 sans-serif" (a size must come before the family).
      for (const m of text.matchAll(/[^-]font\s*:\s*([\d.]+)(px|rem|em)/g)) {
        const size = px(`${m[1]}${m[2]}`, smallest);
        if (size === null || size < MIN_PX) bad.push(`${relative(SRC, f)}: font ${m[1]}${m[2]}`);
      }
    }
    expect(bad).toEqual([]);
  });

  it("sets no chart or inline font size under 14 px in code", () => {
    const bad: string[] = [];
    for (const f of codeFiles) {
      const text = readFileSync(f, "utf8");
      for (const m of text.matchAll(/fontSize\s*:\s*([\d.]+)\s*[,}]/g)) {
        if (Number(m[1]) < MIN_PX) bad.push(`${relative(SRC, f)}: fontSize ${m[1]}`);
      }
      for (const m of text.matchAll(/font-size\s*:\s*([\d.]+)px/g)) {
        if (Number(m[1]) < MIN_PX) bad.push(`${relative(SRC, f)}: font-size ${m[1]}px`);
      }
    }
    expect(bad).toEqual([]);
  });

  it("gives the chart code a text size of at least 14 px", () => {
    expect(CHART_FONT_PX).toBeGreaterThanOrEqual(MIN_PX);
  });
});
