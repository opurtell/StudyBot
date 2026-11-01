import path from "node:path";
import { cloudflareTest, readD1Migrations } from "@cloudflare/vitest-plugin";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    projects: [
      {
        plugins: [
          cloudflareTest(async () => ({
            wrangler: { configPath: "./wrangler.jsonc" },
            miniflare: {
              bindings: {
                TEST_MIGRATIONS: await readD1Migrations(path.join(__dirname, "migrations")),
                TURNSTILE_SECRET_KEY: "test-secret",
                GEMINI_API_KEY: "test-gemini-key",
                AI_GATEWAY_TOKEN: "",
              },
            },
          })),
        ],
        test: {
          name: "worker",
          include: ["test/worker/**/*.test.ts"],
          setupFiles: ["test/worker/apply-migrations.ts"],
        },
      },
      {
        plugins: [react()],
        test: {
          name: "client",
          environment: "jsdom",
          include: ["test/client/**/*.test.tsx"],
          setupFiles: ["test/client/setup.ts"],
        },
      },
    ],
  },
});
