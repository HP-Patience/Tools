import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../../", import.meta.url));
const frontend = path.join(root, "frontend");
const folder = path.join(root, "assets/readme");
await fs.mkdir(path.join(root, ".local"), { recursive: true });
await fs.mkdir(path.join(root, "artifacts"), { recursive: true });
const python =
  process.platform === "win32"
    ? path.join(root, "backend/.venv/Scripts/python.exe")
    : "python3";
const server = spawn(python, [path.join(root, "scripts/readme_preview.py")], {
  cwd: root,
  env: {
    ...process.env,
    APP_DATABASE_PATH: path.join(
      root,
      ".local",
      "readme-" + randomUUID() + ".db",
    ),
    APP_APP_URL: "http://localhost:18772",
    APP_PRODUCTION: "false",
    APP_MAIL_BACKEND: "disabled",
  },
  stdio: "pipe",
});
const vite = spawn(
  process.execPath,
  [
    path.join(frontend, "node_modules/vite/bin/vite.js"),
    "--host",
    "127.0.0.1",
    "--port",
    "18772",
    "--strictPort",
  ],
  {
    cwd: frontend,
    env: { ...process.env, API_PROXY_TARGET: "http://127.0.0.1:18771" },
    stdio: "pipe",
  },
);
let diagnostics = "";
for (const child of [server, vite])
  for (const stream of [child.stdout, child.stderr])
    stream.on("data", (x) => {
      diagnostics += x.toString();
    });
async function ready(url) {
  for (let i = 0; i < 100; i++) {
    if (server.exitCode !== null || vite.exitCode !== null)
      throw new Error(diagnostics);
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error("Preview startup timed out: " + diagnostics);
}
let browser;
try {
  await Promise.all([
    ready("http://127.0.0.1:18771/health/"),
    ready("http://localhost:18772"),
  ]);
  browser = await chromium.launch(
    process.platform === "win32"
      ? {
          executablePath:
            "C:/Program Files/Google/Chrome/Application/chrome.exe",
        }
      : {},
  );
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1060 },
    reducedMotion: "reduce",
  });
  await page.goto("http://localhost:18772");
  await page.getByRole("heading", { name: "设置管理员账户" }).waitFor();
  const secret = randomUUID();
  await page
    .getByRole("textbox", { name: "用户名", exact: true })
    .fill("demo-admin");
  await page.getByRole("textbox", { name: "密码", exact: true }).fill(secret);
  await page
    .getByRole("textbox", { name: "确认密码", exact: true })
    .fill(secret);
  await page
    .getByRole("button", { name: "创建管理员并进入", exact: true })
    .click();
  await page.getByRole("heading", { name: "经营概览." }).waitFor();
  await page.getByText("¥423.00", { exact: true }).first().waitFor();
  await page.screenshot({
    path: path.join(folder, "dashboard.webp"),
    type: "webp",
    quality: 90,
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".mobile-menu").waitFor({ state: "visible" });
  await page.screenshot({
    path: path.join(folder, "mobile.webp"),
    type: "webp",
    quality: 90,
  });
  const svg = await fs.readFile(path.join(folder, "hero.svg"));
  for (const width of [900, 360]) {
    await page.setViewportSize({
      width,
      height: Math.ceil((width * 320) / 1200),
    });
    await page.setContent(
      `<style>html,body{margin:0;background:#fff}img{display:block;width:100%}</style><img alt="hero" src="data:image/svg+xml;base64,${svg.toString("base64")}">`,
    );
    await page.locator("img").evaluate((el) => el.decode());
    await page.screenshot({
      path: path.join(root, "artifacts", "readme-hero-" + width + ".png"),
    });
  }
  console.log(
    "README screenshots captured from isolated demo database; SVG rendered at 900 and 360 px.",
  );
} finally {
  if (browser) await browser.close();
  server.kill();
  vite.kill();
}
