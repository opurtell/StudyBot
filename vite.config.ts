import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  // base: './' produces relative asset paths.
  // Electron's file:// protocol resolves these relative to index.html — correct in both dev and prod.
  build: {
    outDir: "dist",
  },
  server: {
    port: 5173,
    watch: {
      ignored: ["**/data/**"],
    },
  },
  optimizeDeps: {
    entries: ["index.html"],
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["tests/renderer/setup.ts"],
  },
});
