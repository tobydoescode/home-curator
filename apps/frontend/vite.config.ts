import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  // Emit relative asset URLs so they resolve against the `<base href>` the
  // backend injects from Home Assistant's X-Ingress-Path header. With the
  // default absolute base, every asset would resolve against the HA host
  // rather than the add-on and 404 under ingress.
  base: "./",
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8099", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    environmentOptions: { jsdom: { url: "http://localhost/" } },
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    css: true,
  },
});
