// Playwright global setup: the e2e serves the built page from dist, so a missing or older build
// would test something other than the source. Fail at once with the cause, not minutes later
// with a timeout in the middle of a test.
import { readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));

function newest(dir) {
  let latest = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    latest = Math.max(latest, entry.isDirectory() ? newest(path) : statSync(path).mtimeMs);
  }
  return latest;
}

export default function checkDist() {
  let built;
  try {
    built = statSync(join(root, "dist", "index.html")).mtimeMs;
  } catch {
    throw new Error("frontend/dist is missing: run `npm run build` before `npm run e2e`.");
  }
  const edited = Math.max(newest(join(root, "src")), statSync(join(root, "index.html")).mtimeMs);
  if (edited > built) {
    throw new Error("frontend/dist is older than src: run `npm run build` before `npm run e2e`.");
  }
}
