import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const PORT = 8765;
const repoRoot = fileURLToPath(new URL("..", import.meta.url));

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
  timeout: 60_000,
  expect: { timeout: 15_000 },
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
    reuseExistingServer: !process.env["CI"],
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
