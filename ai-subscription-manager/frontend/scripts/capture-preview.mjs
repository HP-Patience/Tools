import { chromium } from "@playwright/test";
import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
// Provide preview-only credentials explicitly after first-run setup.
const credentials = {
  username: process.env.PREVIEW_USERNAME,
  password: process.env.PREVIEW_PASSWORD,
};
if (!credentials.username || !credentials.password)
  throw new Error(
    "先在网页设置管理员，再通过 PREVIEW_USERNAME 和 PREVIEW_PASSWORD 提供截图登录信息",
  );
const browser = await chromium.launch(
  process.platform === "win32"
    ? {
        executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
      }
    : {},
);
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1060 },
  });
  await page.goto("http://localhost:5173");
  await page
    .getByRole("textbox", { name: "用户名", exact: true })
    .fill(credentials.username);
  await page
    .getByRole("textbox", { name: "密码", exact: true })
    .fill(credentials.password);
  await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  await page.getByRole("heading", { name: "经营概览." }).waitFor();
  await page.waitForLoadState("networkidle");
  await fs.mkdir(new URL("../../artifacts/", import.meta.url), {
    recursive: true,
  });
  await page.screenshot({
    path: fileURLToPath(
      new URL("../../artifacts/dashboard-desktop.png", import.meta.url),
    ),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.locator(".mobile-menu").waitFor({ state: "visible" });
  await page.screenshot({
    path: fileURLToPath(
      new URL("../../artifacts/dashboard-mobile.png", import.meta.url),
    ),
    fullPage: true,
  });
  console.log("Desktop and mobile preview screenshots saved.");
} finally {
  await browser.close();
}
