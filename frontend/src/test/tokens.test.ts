import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = resolve(import.meta.dirname, "..");
const css = readFileSync(join(SRC, "styles", "tokens.css"), "utf8");

type Tokens = Record<string, string>;

function declarations(block: string): Tokens {
  const out: Tokens = {};
  for (const m of block.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) out[m[1] as string] = (m[2] as string).trim();
  return out;
}

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

function resolveAll(tokens: Tokens): Tokens {
  const out: Tokens = {};
  const lookup = (name: string, depth = 0): string => {
    const value = tokens[name];
    if (value === undefined || depth > 8) throw new Error(`unresolved ${name}`);
    const ref = /^var\((--[a-z0-9-]+)\)$/.exec(value);
    return ref ? lookup(ref[1] as string, depth + 1) : value;
  };
  for (const name of Object.keys(tokens)) out[name] = lookup(name);
  return out;
}

const light = declarations(ruleBody(css, ":root {"));

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

/** Prototype v4a (README-v4, token table), approved by the owner on 2026-11-19. Light only. */
const DESIGN: Record<string, string> = {
  "--page": "#F4F6FA",
  "--surface": "#FFFFFF",
  "--soft": "#F7F8FB",
  "--line": "#DDE2EC",
  "--grid": "#EBEEF4",
  "--rule": "#0E1430",
  "--mark-ns": "#C3CAD9",
  "--axis": "#7A839E",
  "--ink": "#0E1430",
  "--ink-2": "#4A5470",
  "--accent": "#0B7285",
  "--accent-50": "#EDF6F8",
  "--rail": "#141A33",
  "--rail-cyan": "#3CC8E8",
  "--pos": "#007862",
  "--neg": "#C23345",
  "--caution": "#8A5A00",
  "--neg-50": "#FBE9EC",
  "--pos-t": "#9ECCC3",
  "--neg-t": "#E8B1B8",
  "--border": "#DDE2EC",
  "--focus": "#0B7285",
};

/** Text pairs that must reach 4.5:1, and UI marks that must reach 3:1 (WCAG 2.2, 1.4.3 and 1.4.11). */
const TEXT_PAIRS: [string, string][] = [
  ["--ink", "--page"],
  ["--ink", "--surface"],
  ["--ink-2", "--page"],
  ["--ink-2", "--surface"],
  ["--ink-2", "--soft"],
  ["--ink-3", "--surface"],
  ["--accent", "--surface"],
  ["--accent", "--page"],
  ["--on-accent", "--accent"],
  ["--pos", "--surface"],
  ["--pos", "--page"],
  ["--neg", "--surface"],
  ["--neg", "--page"],
  ["--caution", "--surface"],
  ["--caution", "--page"],
  ["--rail-text", "--rail"],
  ["--rail-2", "--rail"],
  ["--rail-2", "--rail-hover"],
  ["--rail-cyan", "--rail"],
  ["--rail-cyan", "--rail-hover"],
  ["--rail", "--rail-cyan"],
];
const UI_PAIRS: [string, string][] = [
  ["--control-line", "--surface"],
  ["--axis", "--surface"],
  ["--rail-track", "--rail"],
  ["--accent", "--surface"],
];

describe("design tokens (prototype v4a)", () => {
  const resolved = resolveAll(light);

  it.each(Object.entries(DESIGN))("%s is %s", (name, value) => {
    expect(resolved[name]?.toUpperCase()).toBe(value);
  });

  it.each(TEXT_PAIRS)("text %s on %s reaches 4.5:1", (fg, bg) => {
    expect(contrast(resolved[fg] as string, resolved[bg] as string)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(UI_PAIRS)("mark %s on %s reaches 3:1", (fg, bg) => {
    expect(contrast(resolved[fg] as string, resolved[bg] as string)).toBeGreaterThanOrEqual(3);
  });

  it("is light as the base, with a dark set under data-theme and under the system setting", () => {
    expect(ruleBody(css, ":root {")).toMatch(/color-scheme:\s*light/);
    expect(css).toMatch(/prefers-color-scheme: dark/);
    expect(css).toMatch(/data-theme="dark"/);
  });

  it("keeps every type size at 14 px or more", () => {
    const sizes = [...css.matchAll(/--fs-[a-z0-9-]+:\s*(\d+)px/g)].map((m) => Number(m[1]));
    expect(sizes.length).toBeGreaterThanOrEqual(6);
    for (const size of sizes) expect(size).toBeGreaterThanOrEqual(14);
    expect(resolved["--sans"]).toMatch(/^"IBM Plex Sans"/);
  });

  it("caps the canvas at 1680 px beside a rail of 300 to 320 px", () => {
    expect(resolved["--canvas-max"]).toBe("1680px");
    expect(resolved["--side-w"]).toBe("clamp(300px, 22vw, 320px)");
  });
});

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) walk(path, out);
    else out.push(path);
  }
  return out;
}

describe("no colour literals outside tokens.css", () => {
  const files = walk(SRC).filter(
    (f) =>
      /\.(css|ts|tsx)$/.test(f) &&
      !/\.test\.tsx?$/.test(f) &&
      !f.endsWith(join("styles", "tokens.css")) &&
      !f.endsWith("types.gen.ts"),
  );

  it("has files to check", () => {
    expect(files.length).toBeGreaterThan(10);
  });

  it.each(files.map((f) => [relative(SRC, f).replaceAll("\\", "/"), f] as const))("%s", (_name, file) => {
    const text = readFileSync(file, "utf8");
    expect(text.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([]);
    expect(text.match(/\b(?:rgb|rgba|hsl|hsla|oklch|oklab)\(/g) ?? []).toEqual([]);
  });
});

describe("fonts ship in the bundle", () => {
  const fonts = readFileSync(join(SRC, "styles", "fonts.css"), "utf8");
  const urls = [...fonts.matchAll(/url\("([^"]+)"\)/g)].map((m) => m[1] as string);

  it("references the one local IBM Plex Sans WOFF2 file, weights 400 to 700", () => {
    expect(urls).toHaveLength(1);
    expect(fonts).toMatch(/font-family:\s*"IBM Plex Sans"/);
    expect(fonts).toMatch(/font-weight:\s*400 700/);
    for (const url of urls) {
      expect(url.startsWith("../assets/fonts/")).toBe(true);
      expect(existsSync(resolve(SRC, "styles", url))).toBe(true);
    }
  });

  it("names no network host and uses font-display swap", () => {
    expect(fonts).not.toMatch(/https?:\/\//);
    expect(fonts.match(/font-display:\s*swap/g)).toHaveLength(1);
  });

  it("ships the licence texts beside the fonts", () => {
    expect(existsSync(join(SRC, "assets", "fonts", "IBMPlexSans-OFL.txt"))).toBe(true);
  });

  it("loads no external script, style or font in index.html", () => {
    const html = readFileSync(resolve(SRC, "..", "index.html"), "utf8");
    expect(html).not.toMatch(/https?:\/\//);
  });
});
