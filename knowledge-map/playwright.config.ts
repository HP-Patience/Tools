import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: { baseURL: "http://127.0.0.1:5174", trace: "retain-on-failure" },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], channel: "chromium" },
    },
  ],
  webServer: {
    command: "npx tsx scripts/e2e-server.ts",
    url: "http://127.0.0.1:5174",
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
