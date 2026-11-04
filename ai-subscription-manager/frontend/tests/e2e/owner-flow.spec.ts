import { test, expect } from "@playwright/test";
import path from "node:path";
test("客户、上游、购买续费、利润和手机界面", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    Object.defineProperty(crypto, "randomUUID", {
      value: undefined,
      configurable: true,
    });
  });
  await page.goto("/");
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute(
    "href",
    "/favicon.svg",
  );
  await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute(
    "href",
    "/icon.svg",
  );
  await expect(
    page.getByRole("heading", { name: "设置管理员账户" }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "用户名", exact: true })
    .fill("e2e-owner");
  await page
    .getByRole("textbox", { name: "密码", exact: true })
    .fill("e2e-only-password-12345");
  await page
    .getByRole("textbox", { name: "确认密码", exact: true })
    .fill("e2e-only-password-12345");
  await page
    .getByRole("button", { name: "创建管理员并进入", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: "经营概览." })).toBeVisible();
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(
    page.getByRole("heading", { name: "登录你的工作台" }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "用户名", exact: true })
    .fill("e2e-owner");
  await page
    .getByRole("textbox", { name: "密码", exact: true })
    .fill("e2e-only-password-12345");
  await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  await expect(page.getByRole("heading", { name: "经营概览." })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "下一步：确认供货渠道" }),
  ).toBeVisible();
  await page.screenshot({
    path: path.resolve("../artifacts/getting-started-desktop.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "记录购买", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "购买前先准备这些资料" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "添加客户", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("link", { name: "添加第一个上游", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "添加上游渠道" }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "上游渠道名称", exact: true })
    .fill("测试上游");
  await page
    .getByRole("textbox", { name: "渠道网址" })
    .fill("https://example.com");
  await page.getByRole("button", { name: "保存记录" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("link", { name: "商品目录", exact: true }).click();
  await page.getByRole("button", { name: "添加商品" }).click();
  await page
    .getByRole("textbox", { name: "商品名称", exact: true })
    .fill("ChatGPT Plus");
  await page
    .getByLabel("上游渠道", { exact: true })
    .selectOption({ label: "测试上游" });
  await page.getByRole("textbox", { name: "参考采购价（元）" }).fill("60");
  await page.getByRole("textbox", { name: "参考售价（元）" }).fill("100");
  await page.getByRole("spinbutton", { name: "默认期限数量" }).fill("1");
  await expect(page.getByLabel("商品名称", { exact: true })).toHaveAttribute(
    "required",
    "",
  );
  await expect(page.getByText("¥40.00", { exact: true })).toBeVisible();
  const details = page.locator("details").filter({ hasText: "更多商品资料" });
  await expect(details).not.toHaveAttribute("open", "");
  await details.locator("summary").click();
  await expect(
    page.getByLabel("平台，如 OpenAI", { exact: true }),
  ).not.toHaveAttribute("required");
  await page
    .getByLabel("商品链接", { exact: true })
    .fill("https://example.com/product");
  await details.locator("summary").click();
  await page
    .getByLabel("质保条件", { exact: true })
    .fill("掉订阅保30天，封号不保。续费前核对是否覆盖。");
  await page.locator(".form-body").evaluate((el) => (el.scrollTop = 0));
  await page.screenshot({
    path: path.resolve("../artifacts/product-form-desktop.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  const saveBox = await page
    .getByRole("button", { name: "保存记录" })
    .boundingBox();
  expect(
    saveBox && saveBox.y >= 0 && saveBox.y + saveBox.height <= 844,
  ).toBeTruthy();
  expect(
    await page
      .getByRole("dialog")
      .evaluate((el) => el.scrollWidth <= el.clientWidth),
  ).toBeTruthy();
  await page.screenshot({
    path: path.resolve("../artifacts/product-form-mobile.png"),
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "保存记录" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("button", { name: "编辑ChatGPT Plus", exact: true })
    .click();
  await expect(page.getByLabel("质保条件", { exact: true })).toHaveValue(
    "掉订阅保30天，封号不保。续费前核对是否覆盖。",
  );
  await page.getByRole("dialog").locator("details summary").click();
  await expect(page.getByLabel("商品链接", { exact: true })).toHaveValue(
    "https://example.com/product",
  );
  await page.getByRole("button", { name: "取消", exact: true }).click();
  await page
    .getByRole("button", { name: "切换状态ChatGPT Plus", exact: true })
    .click();
  await page.getByRole("button", { name: "确认", exact: true }).click();
  await page.getByRole("link", { name: "经营概览", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "下一步：定价并启用商品" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "去完善并启用商品", exact: true })
    .click();
  await page.locator(".page-guide summary").click();
  await expect(
    page.getByText("保存商品只是建立销售模板", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "切换状态ChatGPT Plus", exact: true })
    .click();
  await page.getByRole("button", { name: "确认", exact: true }).click();
  await page.getByRole("link", { name: "经营概览", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "下一步：添加客户" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "添加第一位客户", exact: true }).click();
  await page
    .getByRole("textbox", { name: "客户名称", exact: true })
    .fill("测试客户");
  await page.getByRole("textbox", { name: "微信号" }).fill("wx_e2e");
  await page.getByRole("textbox", { name: "QQ号" }).fill("123456789");
  await page.getByRole("button", { name: "保存记录" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("link", { name: "经营概览", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "下一步：记录首笔购买" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "记录第一笔购买", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "记录购买", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "取消", exact: true }).click();
  await expect(page).toHaveURL(/\/services$/);
  await page.getByRole("link", { name: "客户管理", exact: true }).click();
  await page.getByRole("link", { name: "测试客户", exact: true }).click();
  await expect(page.getByText("wx_e2e", { exact: true })).toBeVisible();
  for (let i = 0; i < 2; i++) {
    await page.getByRole("button", { name: "记录购买", exact: true }).click();
    await page
      .getByLabel("购买商品", { exact: true })
      .selectOption({ label: "ChatGPT Plus · 测试上游" });
    await page
      .getByRole("textbox", { name: "账号 / 席位标识" })
      .fill("账号" + (i + 1));
    await page.getByRole("button", { name: "保存交易" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  }
  await expect(page.getByText("2 项", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "查看", exact: true }).first().click();
  await page.getByRole("button", { name: "记录续费" }).click();
  await expect(
    page.getByRole("textbox", { name: "实际采购成本（元）" }),
  ).toHaveValue("60");
  await page.getByRole("button", { name: "保存交易" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByText("续费 · 测试上游", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "经营概览", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "基础资料已就绪，接下来跟进订阅与续费" }),
  ).toBeVisible();
  await expect(
    page.getByText("¥120.00", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: path.resolve("../artifacts/dashboard-e2e.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "邮件提醒", exact: true }).click();
  await page
    .getByRole("textbox", { name: "接收提醒的邮箱" })
    .fill("test@example.com");
  await page.getByRole("button", { name: "保存设置" }).click();
  await expect(page.getByText("提醒邮箱已保存", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("link", { name: "客户管理", exact: true }).click();
  await page.getByRole("link", { name: "测试客户", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "测试客户", exact: true }),
  ).toBeVisible();
  expect(
    await page.locator("html").evaluate((el) => el.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await page.screenshot({
    path: path.resolve("../artifacts/mobile-e2e.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("link", { name: "经营概览", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "基础资料已就绪，接下来跟进订阅与续费" }),
  ).toBeVisible();
  expect(
    await page.locator("html").evaluate((el) => el.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await page.screenshot({
    path: path.resolve("../artifacts/getting-started-mobile.png"),
    animations: "disabled",
  });
  await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("link", { name: "使用指南", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "使用指南", exact: true }),
  ).toBeVisible();
  expect(
    await page.locator("html").evaluate((el) => el.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await page.screenshot({
    path: path.resolve("../artifacts/usage-guide-mobile.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(
    page.getByRole("heading", { name: "登录你的工作台" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("普通 HTTP 环境也能生成交易提交标识", async ({ page }) => {
  await page.goto("/");
  const ids = await page.evaluate(async () => {
    Object.defineProperty(crypto, "randomUUID", {
      value: undefined,
      configurable: true,
    });
    const { newSubmissionId } = await import("/src/api/id.ts");
    return Array.from({ length: 100 }, () => newSubmissionId());
  });
  expect(new Set(ids).size).toBe(100);
  for (const id of ids)
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
});
