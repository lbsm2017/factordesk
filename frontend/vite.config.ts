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
  build: { outDir: "dist", sourcemap: false, assetsInlineLimit: 0 },
});
