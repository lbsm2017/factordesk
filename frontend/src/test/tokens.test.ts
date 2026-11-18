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

/** Body of the first rule at or after `from` whose selector text contains `selector` (braces balanced). */
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
const darkOverrides = declarations(
  ruleBody(ruleBody(css, "@media (prefers-color-scheme: dark)"), ':root:where(:not([data-theme="light"]))'),
);
const darkAttr = declarations(ruleBody(css, ':root[data-theme="dark"]'));
const dark = { ...light, ...darkOverrides };

/** docs/design/report-design.md section A: named palette and semantic tokens, [light, dark]. */
const DESIGN: Record<string, [string, string]> = {
  "--chalk": ["#edf0f3", "#0e1318"],
  "--sheet": ["#ffffff", "#151b22"],
  "--graphite": ["#16202b", "#e8edf2"],
  "--slate": ["#465361", "#b0bbc6"],
  "--cobalt": ["#2a5bc0", "#5f8ae6"],
  "--copper": ["#b4560c", "#d27c2e"],
  "--page": ["#edf0f3", "#0e1318"],
  "--surface": ["#ffffff", "#151b22"],
  "--sunk": ["#f5f7f9", "#1b232c"],
  "--border": ["#d3d9e0", "#2c3743"],
  "--grid": ["#e5e9ee", "#212a34"],
  "--axis": ["#8a95a2", "#66727f"],
  "--ink": ["#16202b", "#e8edf2"],
  "--ink-2": ["#465361", "#b0bbc6"],
  "--ink-3": ["#5f6b78", "#8f9ba8"],
  "--ink-faded": ["#777e85", "#8a929b"],
  "--accent": ["#16202b", "#e8edf2"],
  "--focus": ["#16202b", "#e8edf2"],
  "--pos": ["#2a5bc0", "#5f8ae6"],
  "--neg": ["#b4560c", "#d27c2e"],
  "--f1": ["#7559c5", "#7053be"],
  "--f2": ["#066e33", "#19783c"],
  "--f3": ["#c25078", "#cb587f"],
  "--f4": ["#1995ba", "#1493b8"],
  "--f5": ["#a18a21", "#aa932d"],
};

describe("design tokens (report-design.md section A)", () => {
  const lightResolved = resolveAll(light);
  const darkResolved = resolveAll(dark);

  it.each(Object.entries(DESIGN))("%s matches the design in light and dark", (name, [l, d]) => {
    expect(lightResolved[name]).toBe(l);
    expect(darkResolved[name]).toBe(d);
  });

  it("html[data-theme=dark] sets exactly the same dark values as the media query", () => {
    expect(darkAttr).toEqual(darkOverrides);
  });

  it("lets html[data-theme=light] stay light under a dark OS (the media rule excludes it)", () => {
    expect(css).toContain(':root:where(:not([data-theme="light"]))');
  });

  it("uses the 1216 px column width in the report stylesheet", () => {
    const report = readFileSync(join(SRC, "styles", "report.css"), "utf8");
    expect(report).toMatch(/\.report\s*\{[^}]*max-width:\s*1216px/);
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

  it("references four local WOFF2 files that exist", () => {
    expect(urls).toHaveLength(4);
    for (const url of urls) {
      expect(url.startsWith("../assets/fonts/")).toBe(true);
      expect(existsSync(resolve(SRC, "styles", url))).toBe(true);
    }
  });

  it("names no network host and uses font-display swap", () => {
    expect(fonts).not.toMatch(/https?:\/\//);
    expect(fonts.match(/font-display:\s*swap/g)).toHaveLength(4);
  });

  it("ships the licence texts beside the fonts", () => {
    expect(existsSync(join(SRC, "assets", "fonts", "InstrumentSans-OFL.txt"))).toBe(true);
    expect(existsSync(join(SRC, "assets", "fonts", "STIXTwo-OFL.txt"))).toBe(true);
  });

  it("loads no external script, style or font in index.html", () => {
    const html = readFileSync(resolve(SRC, "..", "index.html"), "utf8");
    expect(html).not.toMatch(/https?:\/\//);
  });
});
