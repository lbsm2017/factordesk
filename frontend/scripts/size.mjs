// Size budget for the initial JavaScript of the built dashboard.
// Initial JS = the entry script plus every modulepreload chunk named in dist/index.html.
// Lazy chunks (ECharts) are listed for information and do not count against the budget.
// Run `npm run build` first. Sizes are in kB of 1000 bytes.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

// Measured on 2026-11-18: 372.2 kB raw, 114.4 kB gzip. Raw raised from 400 to 405 kB on 2026-11-19 for the
// Summary panel (verdict text, readings and two tables); the gzip budget is unchanged.
const BUDGET_RAW_KB = 405;
const BUDGET_GZIP_KB = 125;

const dist = fileURLToPath(new URL("../dist", import.meta.url));
const html = readFileSync(join(dist, "index.html"), "utf8");

const initial = new Set();
for (const m of html.matchAll(/<(?:script|link)\b[^>]*>/g)) {
  const tag = m[0];
  const isScript = tag.startsWith("<script") && /type="module"/.test(tag);
  const isPreload = /rel="modulepreload"/.test(tag);
  if (!isScript && !isPreload) continue;
  const href = /(?:src|href)="([^"]+)"/.exec(tag)?.[1];
  if (href) initial.add(href.replace(/^\//, ""));
}
if (initial.size === 0) {
  console.error("size: no script found in dist/index.html. Run `npm run build` first.");
  process.exit(2);
}

const kb = (bytes) => (bytes / 1000).toFixed(1);
const measure = (file) => {
  const buf = readFileSync(join(dist, file));
  return { file, raw: buf.length, gzip: gzipSync(buf).length };
};

const rows = [...initial].map(measure);
const total = rows.reduce((t, r) => ({ raw: t.raw + r.raw, gzip: t.gzip + r.gzip }), { raw: 0, gzip: 0 });

console.log("Initial JS");
for (const r of rows) console.log(`  ${r.file.padEnd(40)} ${kb(r.raw).padStart(8)} kB raw ${kb(r.gzip).padStart(8)} kB gzip`);
console.log(
  `  ${"total".padEnd(40)} ${kb(total.raw).padStart(8)} kB raw ${kb(total.gzip).padStart(8)} kB gzip` +
    `   (budget ${BUDGET_RAW_KB} / ${BUDGET_GZIP_KB})`,
);

const lazy = readdirSync(join(dist, "assets"))
  .filter((f) => f.endsWith(".js") && !initial.has(`assets/${f}`))
  .map((f) => measure(`assets/${f}`));
if (lazy.length > 0) {
  console.log("Lazy JS (not in the budget)");
  for (const r of lazy) console.log(`  ${r.file.padEnd(40)} ${kb(r.raw).padStart(8)} kB raw ${kb(r.gzip).padStart(8)} kB gzip`);
}

const failures = [];
if (total.raw > BUDGET_RAW_KB * 1000) failures.push(`raw ${kb(total.raw)} kB is over ${BUDGET_RAW_KB} kB`);
if (total.gzip > BUDGET_GZIP_KB * 1000) failures.push(`gzip ${kb(total.gzip)} kB is over ${BUDGET_GZIP_KB} kB`);
if (failures.length > 0) {
  console.error(`size: initial JS over budget: ${failures.join("; ")}`);
  process.exit(1);
}
console.log("size: within budget");
