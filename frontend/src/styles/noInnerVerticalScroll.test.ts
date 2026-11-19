import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

/** Every .css file under `dir`. */
function cssFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return cssFiles(path);
    return path.endsWith(".css") ? [path] : [];
  });
}

describe("no scrollbar inside a panel", () => {
  it("every rule that scrolls sideways also fixes overflow-y, so a 1px overflow never adds a vertical bar", () => {
    const files = cssFiles(resolve(import.meta.dirname, ".."));
    const bad: string[] = [];
    for (const file of files) {
      const css = readFileSync(file, "utf8");
      for (const rule of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
        const body = rule[2] ?? "";
        if (/overflow-x\s*:\s*(auto|scroll)/.test(body) && !/overflow-y\s*:\s*(hidden|clip|visible)/.test(body)) {
          bad.push(`${file}: ${(rule[1] ?? "").trim()}`);
        }
        if (/overflow-y\s*:\s*(auto|scroll)/.test(body) && !/max-height|height\s*:/.test(body)) {
          // Only the sidebar scrolls vertically (the page shell), by design.
          if (!/side-scroll/.test(rule[1] ?? "")) bad.push(`${file}: ${(rule[1] ?? "").trim()}`);
        }
      }
    }
    expect(bad).toEqual([]);
  });
});
