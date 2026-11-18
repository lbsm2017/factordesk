import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const repoRoot = fileURLToPath(new URL("..", import.meta.url));

/**
 * One port per checkout: several worktrees can run the e2e at once, and a server reused from
 * another worktree would serve a different build and make the result meaningless. The port comes
 * from `E2E_PORT` or from a hash of this checkout's path (8800 to 8999).
 */
function portFor(path: string): number {
  let h = 0;
  for (const ch of path) h = (h * 31 + ch.charCodeAt(0)) % 200;
  return 8800 + h;
}
const PORT = Number(process.env["E2E_PORT"] ?? portFor(repoRoot));

/**
 * Browser smoke test against the fake backend (dashboard spec DB8.2). The fake app serves the
 * built page, so run `npm run build` first. Locally the installed Google Chrome is used; with
 * `CI` set, the Chromium that `npx playwright install chromium` downloads.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  reporter: [["list"]],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  // The first report of a run is computed from scratch (about 5 s on a quiet machine, the Kalman
  // section being the largest part) and the machine may be busy with other work: 3 to 4 times
  // slower made the smoke test fail on a first run and pass on the second. Generous limits cost
  // nothing when the page is fast.
  timeout: 180_000,
  expect: { timeout: 30_000 },
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    ...(process.env["CI"] ? {} : { channel: "chrome" }),
    viewport: { width: 1440, height: 900 },
    trace: "off",
  },
  webServer: {
    command: `uv run uvicorn factordesk.tests.fixtures.fake_app:create --factory --host 127.0.0.1 --port ${PORT}`,
    cwd: repoRoot,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
