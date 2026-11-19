import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@fixtures": fileURLToPath(new URL("../backend/factordesk/tests/fixtures", import.meta.url)),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
    fs: { allow: [".."] },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    assetsInlineLimit: 0,
    // ECharts and zrender are the lazy chunk (about 545 kB raw, loaded after the page frame paints), so
    // the default 500 kB warning does not apply to them. The initial JS has its own budget: `npm run size`.
    chunkSizeWarningLimit: 600,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: "react", test: /node_modules[/\\](react|react-dom|scheduler)[/\\]/, priority: 30 },
            { name: "query", test: /node_modules[/\\]@tanstack[/\\]/, priority: 20 },
            { name: "echarts", test: /node_modules[/\\](echarts|zrender|tslib)[/\\]/, priority: 10 },
          ],
        },
      },
    },
  },
});
