import { chromium, expect } from "@playwright/test";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
const directory = path.resolve("work/production-smoke");
const realMap = JSON.parse(await readFile("data/map.json", "utf8"));
const otherMap = JSON.parse(await readFile("data/maps/new-atlas.json", "utf8"));
await mkdir(directory, { recursive: true });
const browser = await chromium.launch({ channel: "chromium" });
try {
  const context = await browser.newContext({
    httpCredentials: {
      username: process.env.ATLAS_SMOKE_USER,
      password: process.env.ATLAS_SMOKE_PASSWORD,
    },
    viewport: { width: 1440, height: 960 },
  });
  const page = await context.newPage();
  const problems = [];
  page.on("pageerror", (error) => {
    problems.push(error.message);
    console.error("Page error:", error.message);
  });
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type()))
      problems.push(message.text());
  });
  await page.goto(process.env.ATLAS_SMOKE_URL);
  const catalog = page.getByRole("combobox", { name: "切换知识地图" });
  await expect(catalog).toHaveValue(realMap.id);
  await expect(catalog.locator(`option[value="${realMap.id}"]`)).toHaveText(
    realMap.title,
  );
  if (realMap.nodes.length) {
    await expect(
      page.getByRole("heading", { name: realMap.title, exact: true }),
    ).toBeVisible();
    const node = realMap.nodes.find((item) => item.summary) ?? realMap.nodes[0];
    await page
      .getByRole("button", { name: `查看知识点：${node.title}`, exact: true })
      .click();
    const detail = page.getByTestId("node-detail");
    await detail
      .getByRole("button", { name: "全屏展示详情", exact: true })
      .click();
    await detail.getByTestId("node-body").locator("summary").click();
    expect(await detail.locator("#node-summary").textContent()).toBe(
      node.summary || "先留一个位置，还没有补充详细内容。",
    );
    await page.keyboard.press("Escape");
    await detail
      .getByRole("button", { name: "关闭节点详情", exact: true })
      .click();
  } else {
    await expect(
      page.getByRole("heading", { name: "你的知识地图，从这里开始" }),
    ).toBeVisible();
  }
  await page.screenshot({ path: path.join(directory, "personal.png") });
  await catalog.selectOption(otherMap.id);
  await expect(catalog).toHaveValue(otherMap.id);
  await expect(catalog.locator(`option[value="${otherMap.id}"]`)).toHaveText(
    otherMap.title,
  );
  await page.reload();
  await expect(catalog).toHaveValue(otherMap.id);
  if (!otherMap.nodes.length) {
    await expect(
      page.getByRole("heading", { name: "你的知识地图，从这里开始" }),
    ).toBeVisible();
  } else {
    await expect(
      page.getByRole("heading", { name: otherMap.title, exact: true }),
    ).toBeVisible();
  }
  await catalog.selectOption("__demo__");
  await expect(
    page.getByRole("button", { name: "查看知识点：过拟合", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "只读查看", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "折叠评估与泛化", exact: true })
    .click();
  await page.getByRole("textbox", { name: "搜索知识点" }).fill("过拟合");
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "过拟合", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "清空搜索" }).click();
  await page.getByRole("button", { name: "回到全图" }).click();
  // React Flow fitView uses a 240ms viewport animation; unrelated edge animations may be infinite.
  await page.waitForTimeout(350);
  await page.screenshot({ path: path.join(directory, "desktop.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "过拟合", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "回到全图" }).click();
  await page.waitForTimeout(350);
  await page.screenshot({ path: path.join(directory, "mobile.png") });
  await page
    .getByRole("button", { name: "展开详情", exact: true })
    .first()
    .click();
  await page
    .getByTestId("node-detail")
    .getByText("更多内容", { exact: true })
    .click();
  await expect(page.getByRole("heading", { name: "学习来源" })).toBeVisible();
  await page.screenshot({ path: path.join(directory, "mobile-details.png") });
  for (const viewport of [
    { width: 320, height: 568 },
    { width: 768, height: 1024 },
    { width: 1024, height: 768 },
  ]) {
    await page.setViewportSize(viewport);
    await page.reload();
    await expect(
      page.getByRole("button", { name: "查看知识点：过拟合", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const box = await page.getByTestId("map-canvas").boundingBox();
    expect(box.height).toBeGreaterThan(0);
  }
  expect(problems).toEqual([]);
  console.log(
    "Production browser passed: personal maps/demo, fullscreen reading, interactions, desktop/mobile/tablet, no console/CSP errors.",
  );
  await context.close();
} finally {
  await browser.close();
}
