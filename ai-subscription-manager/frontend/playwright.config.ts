import { defineConfig } from "@playwright/test";
import path from "node:path";
import { randomUUID } from "node:crypto";
const python =
  process.env.E2E_PYTHON ||
  (process.platform === "win32"
    ? "../backend/.venv/Scripts/python.exe"
    : "python");
const db = path.resolve("../.local/e2e-" + randomUUID() + ".db");
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 45000,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:18762",
    trace: "retain-on-failure",
    launchOptions:
      process.platform === "win32"
        ? {
            executablePath:
              "C:/Program Files/Google/Chrome/Application/chrome.exe",
          }
        : {},
  },
  webServer: [
    {
      command: `"${python}" ../backend/tests/serve_e2e.py`,
      url: "http://127.0.0.1:18761/health/",
      reuseExistingServer: false,
      timeout: 60000,
      env: {
        APP_DATABASE_PATH: db,
        APP_APP_URL: "http://localhost:18762",
        APP_PRODUCTION: "false",
        APP_MAIL_BACKEND: "disabled",
      },
    },
    {
      command: "npm run dev -- --port 18762",
      url: "http://localhost:18762",
      reuseExistingServer: false,
      timeout: 60000,
      env: { API_PROXY_TARGET: "http://127.0.0.1:18761" },
    },
  ],
});
