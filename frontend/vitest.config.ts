import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@fixtures": fileURLToPath(new URL("../backend/factordesk/tests/fixtures", import.meta.url)),
    },
  },
  server: { fs: { allow: [".."] } },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
    css: false,
    // Local runs use 3 workers so the PC stays usable; CI machines are dedicated and keep the default.
    maxWorkers: process.env.CI ? undefined : 3,
  },
});
