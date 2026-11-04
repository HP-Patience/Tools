import { test, expect } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";
import demo from "../../examples/machine-learning.json" with { type: "json" };
import type { KnowledgeMap } from "../../src/core/types.ts";
const fixture = ".local/e2e-map.json";
const empty = JSON.stringify({
  schemaVersion: 1,
  id: "my-map",
  title: "我的知识地图",
  description: "",
  updatedAt: "2026-09-10T00:00:00Z",
  nodes: [],
  relations: [],
  sources: [],
});
test.beforeEach(async () => {
  await writeFile(fixture, empty);
});
test("真实空白与示例隔离，页面只读", async ({ page }) => {
  const original = await readFile("data/map.json", "utf8");
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "你的知识地图，从这里开始" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "先看看示例地图" }).click();
  await expect(
    page.getByRole("heading", { name: "过拟合", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("不代表你的学习记录")).toBeVisible();
  expect(await page.locator('[contenteditable="true"],textarea').count()).toBe(
    0,
  );
  await page
    .getByRole("button", { name: "返回我的地图", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "你的知识地图，从这里开始" }),
  ).toBeVisible();
  expect(await readFile("data/map.json", "utf8")).toBe(original);
});
test("折叠、搜索隐藏节点、无结果、关系导航与键盘", async ({ page }) => {
  await page.goto("/?demo=1");
  await page
    .getByRole("button", { name: "折叠评估与泛化", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "查看知识点：过拟合", exact: true }),
  ).toHaveCount(0);
  await page.keyboard.press("Control+k");
  await page.getByRole("textbox", { name: "搜索知识点" }).fill("过拟合");
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "查看知识点：过拟合", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "过拟合", exact: true }),
  ).toBeVisible();
  await page
    .getByTestId("node-detail")
    .getByText("更多内容", { exact: true })
    .click();
  await page
    .getByTestId("node-detail")
    .getByRole("button", { name: /模型复杂度/ })
    .click();
  await expect(
    page.getByRole("heading", { name: "模型复杂度", exact: true }),
  ).toBeVisible();
  await page.getByRole("textbox", { name: "搜索知识点" }).fill("不存在的词");
  await expect(page.getByText("没有找到对应知识点")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("node-detail")).toHaveCount(0);
});
test("有效热更新、非法文件保留、重试保留、删除节点清理", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "你的知识地图，从这里开始" }),
  ).toBeVisible();
  const data = structuredClone(demo) as KnowledgeMap;
  await writeFile(fixture, JSON.stringify(data));
  await expect(
    page.getByRole("button", { name: "查看知识点：过拟合", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "查看知识点：过拟合", exact: true })
    .click();
  await writeFile(fixture, '{"broken":');
  await expect(page.getByRole("alert")).toContainText("已保留上一份有效地图");
  await page.getByRole("button", { name: "重试", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("已保留上一份有效地图");
  await expect(
    page.getByRole("heading", { name: "过拟合", exact: true }),
  ).toBeVisible();
  data.nodes = data.nodes.filter((n) => n.id !== "overfit");
  data.relations = data.relations.filter(
    (r) => r.source !== "overfit" && r.target !== "overfit",
  );
  await writeFile(fixture, JSON.stringify(data));
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByTestId("node-detail")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "查看知识点：过拟合", exact: true }),
  ).toHaveCount(0);
});

test("节点可以自由拖动", async ({ page }) => {
  await page.goto("/?demo=1");
  const node = page.getByRole("button", {
    name: "查看知识点：过拟合",
    exact: true,
  });
  await expect(node).toBeVisible();
  const before = await node.boundingBox();
  expect(before).not.toBeNull();
  await page.mouse.move(
    before!.x + before!.width / 2,
    before!.y + before!.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    before!.x + before!.width / 2 + 120,
    before!.y + before!.height / 2 + 40,
    { steps: 8 },
  );
  await page.mouse.up();
  await expect
    .poll(async () => {
      const after = await node.boundingBox();
      return Math.round((after?.x ?? 0) - before!.x);
    })
    .toBeGreaterThan(50);
});

test("待归类和不可信文字安全展示", async ({ page }) => {
  const data = structuredClone(demo) as KnowledgeMap;
  data.nodes.push({
    ...data.nodes[0],
    id: "pending",
    title: "临时想法",
    summary: "<img src=x onerror=alert(1)>",
    parentId: null,
    placement: "unassigned",
  });
  await writeFile(fixture, JSON.stringify(data));
  await page.goto("/");
  await page.getByRole("button", { name: /待归类/ }).click();
  await page.getByRole("button", { name: "查看知识点：临时想法" }).click();
  await expect(page.getByTestId("node-detail")).toContainText(
    "<img src=x onerror=alert(1)>",
  );
  expect(await page.getByTestId("node-detail").locator("img").count()).toBe(0);
  await expect(
    page.getByRole("button", { name: "查看知识点：机器学习" }),
  ).toHaveCount(0);
});
test("手机搜索、导航、详情展开和画布操作", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?demo=1");
  await expect(
    page.getByRole("heading", { name: "过拟合", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "展开详情", exact: true })
    .first()
    .click();
  await page
    .getByTestId("node-detail")
    .getByText("更多内容", { exact: true })
    .click();
  await expect(page.getByRole("heading", { name: "学习来源" })).toBeVisible();
  await page.getByRole("button", { name: "关闭节点详情" }).click();
  await page.getByRole("button", { name: "打开搜索" }).click();
  await page.getByRole("textbox", { name: "搜索知识点" }).fill("损失函数");
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "损失函数", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "关闭节点详情" }).click();
  await page.getByRole("button", { name: "打开知识导航" }).click();
  await page.getByRole("button", { name: /全部知识/ }).click();
  await page.getByRole("button", { name: "放大地图" }).click();
  await page.getByRole("button", { name: "回到全图" }).click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("常规页面无浏览器错误及 ReactFlow 警告", async ({ page }) => {
  const problems: string[] = [];
  page.on("pageerror", (e) => problems.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error" || m.type() === "warning") problems.push(m.text());
  });
  await page.goto("/?demo=1");
  await expect(
    page.getByRole("button", { name: "查看知识点：过拟合", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "回到全图" }).click();
  expect(problems).toEqual([]);
});

test("搜索定位后全图按钮确实容纳所有节点", async ({ page }) => {
  await page.goto("/?demo=1");
  await page.getByRole("textbox", { name: "搜索知识点" }).fill("过拟合");
  await page.keyboard.press("Enter");
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const canvas = document
          .querySelector('[data-testid="map-canvas"]')!
          .getBoundingClientRect();
        const node = document
          .querySelector('.react-flow__node[data-id="overfit"]')!
          .getBoundingClientRect();
        return (
          Math.abs(node.x + node.width / 2 - canvas.x - canvas.width / 2) < 2 &&
          Math.abs(node.y + node.height / 2 - canvas.y - canvas.height / 2) < 2
        );
      }),
    )
    .toBe(true);
  await page.getByRole("button", { name: "回到全图" }).click();
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const canvas = document
          .querySelector('[data-testid="map-canvas"]')!
          .getBoundingClientRect();
        return [...document.querySelectorAll(".react-flow__node")].every(
          (node) => {
            const box = node.getBoundingClientRect();
            return (
              box.left >= canvas.left - 1 &&
              box.right <= canvas.right + 1 &&
              box.top >= canvas.top - 1 &&
              box.bottom <= canvas.bottom + 1
            );
          },
        );
      }),
    )
    .toBe(true);
});

for (const width of [1000, 1440, 1800]) {
  test(`桌面 ${width}px 侧栏收起释放空间且保留节点与专注状态`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/?demo=1");
    const sidebar = page.locator("#knowledge-sidebar");
    const canvas = page.getByTestId("map-canvas");
    await expect(sidebar).toBeVisible();
    await expect(page.getByTestId("node-detail")).toContainText("过拟合");
    const before = await canvas.boundingBox();
    const sidebarBox = await sidebar.boundingBox();
    await page.getByRole("button", { name: "收起左侧边栏" }).click();
    await expect(sidebar).toBeHidden();
    await expect(
      page.getByRole("button", { name: "展开左侧边栏" }),
    ).toBeFocused();
    await expect
      .poll(async () => (await canvas.boundingBox())!.width)
      .toBeGreaterThan(before!.width + sidebarBox!.width - 2);
    await expect(page.getByTestId("node-detail")).toContainText("过拟合");
    await page.getByRole("button", { name: "进入专注画布" }).click();
    await expect(page.getByRole("banner")).toBeHidden();
    await page.keyboard.press("Escape");
    await expect(sidebar).toBeHidden();
    await page.getByRole("button", { name: "展开左侧边栏" }).click();
    await expect(sidebar).toBeVisible();
    await expect(
      page.getByRole("button", { name: "收起左侧边栏" }),
    ).toBeFocused();
    await expect
      .poll(async () => (await canvas.boundingBox())!.width)
      .toBe(before!.width);
    await page.getByRole("button", { name: "关闭节点详情" }).click();
    await page.getByRole("button", { name: "收起左侧边栏" }).click();
    await expect
      .poll(async () => (await canvas.boundingBox())!.width)
      .toBe(width);
    // Desktop state must not prevent the mobile drawer from opening.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("button", { name: "打开知识导航" }).click();
    await expect(sidebar).toBeVisible();
    await expect(
      page.getByRole("button", { name: "收起左侧边栏" }),
    ).toBeHidden();
    await page.getByRole("button", { name: "关闭导航", exact: true }).click();
    await expect(sidebar).toBeHidden();
  });
}

test("界面移除装饰文案但保留必要标签和示例提醒", async ({ page }) => {
  await page.goto("/?demo=1");
  await expect(page.getByText("不代表你的学习记录")).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "切换知识地图" }),
  ).toBeVisible();
  await expect(page.getByRole("img", { name: "只读查看" })).toBeVisible();
  for (const text of [
    "PERSONAL ATLAS",
    "MY KNOWLEDGE MAP",
    "我的知识，慢慢长成体系。",
    "为理解留下位置",
    "点击节点，展开理解",
    "持续整理中",
    "尚未发布的修改不会同步到服务器",
  ]) {
    await expect(page.getByText(text, { exact: true })).toHaveCount(0);
  }
  await page.getByRole("button", { name: "进入专注画布" }).click();
  await expect(page.getByText("知识关联", { exact: true })).toBeHidden();
  await expect(
    page.getByRole("button", { name: "退出专注画布" }),
  ).toBeVisible();
});

test("桌面端详情窗口可拖拽调整宽度，移动端不显示拖拽条", async ({ page }) => {
  await page.goto("/?demo=1");
  const detail = page.getByTestId("node-detail");
  const handle = page.getByRole("separator", { name: "调整详情窗口宽度" });
  const before = await detail.evaluate(
    (el) => el.getBoundingClientRect().width,
  );
  const box = await handle.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + 5, box!.y + 200);
  await page.mouse.down();
  await page.mouse.move(box!.x - 90, box!.y + 200);
  await page.mouse.up();
  const after = await detail.evaluate((el) => el.getBoundingClientRect().width);
  expect(after).toBeGreaterThan(before + 50);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(handle).toBeHidden();
});

test("详情先显示摘要，其他内容可展开收起", async ({ page }) => {
  await page.goto("/?demo=1");
  const detail = page.getByTestId("node-detail");
  await expect(
    detail.getByRole("heading", { name: "一段话描述" }),
  ).toBeVisible();
  await expect(detail.getByTestId("node-overview")).toContainText(
    "先留一个位置，还没有补充一段话描述。",
  );
  const more = detail.locator("details").filter({ hasText: "更多内容" });
  await expect(more).toBeVisible();
  await expect(more).not.toHaveAttribute("open", "");
  await expect(more.getByRole("heading", { name: "学习来源" })).toBeHidden();
  await more.locator("summary").click();
  await expect(more).toHaveAttribute("open", "");
  await expect(more.getByRole("heading", { name: "学习来源" })).toBeVisible();
  await more.locator("summary").click();
  await expect(more).not.toHaveAttribute("open", "");
  await expect(more.getByRole("heading", { name: "学习来源" })).toBeHidden();
});

for (const width of [390, 1440]) {
  test(`教材阅读 ${width}px 概览完整、正文与原话独立折叠、切换重置`, async ({
    page,
  }) => {
    const data = structuredClone(demo) as KnowledgeMap;
    const target = data.nodes.find((n) => n.id === "overfit")!;
    target.provenance = "material";
    target.overview = "这是概括整个知识节点的一段话，不能截断成三行。".repeat(
      8,
    );
    target.summary =
      "教材正文：需要保留完整的条件、解释与推导。\n".repeat(30) +
      "正文最后一句。";
    target.originalExpression = "这是当时的原话，不能被教材式正文替换。";
    const other = data.nodes.find((n) => n.id === "complexity")!;
    other.originalExpression = "另一个节点的原话。";
    await writeFile(fixture, JSON.stringify(data));
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await page
      .getByRole("button", { name: "查看知识点：过拟合", exact: true })
      .click();
    const detail = page.getByTestId("node-detail");
    const overview = detail.getByTestId("node-overview").locator("p");
    const body = detail.getByTestId("node-body");
    const original = detail.getByTestId("node-original");
    const text = body.locator("#node-summary");
    await expect(overview).toHaveText(target.overview);
    expect(
      await overview.evaluate((el) => el.scrollHeight <= el.clientHeight + 1),
    ).toBe(true);
    await expect(body).not.toHaveAttribute("open", "");
    await expect(original).not.toHaveAttribute("open", "");
    await expect(text).toBeHidden();
    // Original wording is accessible even while the learning body is closed.
    await original.locator("summary").click();
    await expect(original.locator("p")).toBeVisible();
    await expect(original.locator("p")).toHaveText(target.originalExpression);
    await expect(body).not.toHaveAttribute("open", "");
    // Native summary controls also work with a keyboard.
    await body.locator("summary").focus();
    await page.keyboard.press("Enter");
    await expect(body).toHaveAttribute("open", "");
    await expect(text).toBeVisible();
    await expect(text).toHaveText(target.summary);
    expect(
      await text.evaluate((el) => ({
        clipped: el.scrollHeight > el.clientHeight + 1,
        clamp: getComputedStyle(el).webkitLineClamp,
      })),
    ).toEqual({ clipped: false, clamp: "none" });
    await text.scrollIntoViewIfNeeded();
    expect(
      await detail.evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
    ).toBe(true);
    await body.locator("summary").click();
    await expect(text).toBeHidden();
    await expect(original).toHaveAttribute("open", "");
    await original.locator("summary").click();
    await expect(original.locator("p")).toBeHidden();
    await body.locator("summary").click();
    await original.locator("summary").click();
    // Navigate without unmounting the details component.
    if (width === 390)
      await detail
        .getByRole("button", { name: "展开详情", exact: true })
        .first()
        .click();
    await detail.getByText("更多内容", { exact: true }).click();
    await detail.getByRole("button", { name: /模型复杂度/ }).click();
    await expect(
      detail.getByRole("heading", { name: "模型复杂度", exact: true }),
    ).toBeVisible();
    await expect(body).not.toHaveAttribute("open", "");
    await expect(original).not.toHaveAttribute("open", "");
    await expect(original.locator("p")).toHaveText(other.originalExpression);
  });
}

test("空正文有占位、无原话不显示入口、正文不执行 HTML", async ({ page }) => {
  const data = structuredClone(demo) as KnowledgeMap;
  const target = data.nodes.find((n) => n.id === "overfit")!;
  target.summary = "";
  delete target.originalExpression;
  await writeFile(fixture, JSON.stringify(data));
  await page.goto("/");
  await page
    .getByRole("button", { name: "查看知识点：过拟合", exact: true })
    .click();
  const detail = page.getByTestId("node-detail");
  await expect(detail.getByTestId("node-original")).toHaveCount(0);
  await detail.getByTestId("node-body").locator("summary").click();
  await expect(detail.locator("#node-summary")).toHaveText(
    "先留一个位置，还没有补充详细内容。",
  );
  target.summary = '<img src=x onerror="window.__injected=true">';
  await writeFile(fixture, JSON.stringify(data));
  await expect(detail.locator("#node-summary")).toHaveText(target.summary);
  await expect(detail.locator("#node-summary img")).toHaveCount(0);
});

test("详情拖拽不受旧宽度上限与下限限制", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/?demo=1");
  const detail = page.getByTestId("node-detail");
  const handle = page.getByRole("separator", { name: "调整详情窗口宽度" });
  const resize = async (delta: number) => {
    const box = (await handle.boundingBox())!;
    await page.mouse.move(box.x + 7, box.y + 200);
    await page.mouse.down();
    await page.mouse.move(box.x + 7 - delta, box.y + 200, { steps: 5 });
    await page.mouse.up();
  };
  await resize(450);
  expect((await detail.boundingBox())!.width).toBeGreaterThan(700);
  await resize(-560);
  expect((await detail.boundingBox())!.width).toBeLessThan(280);
  await resize(300);
  expect((await detail.boundingBox())!.width).toBeGreaterThan(400);
  await page.setViewportSize({ width: 800, height: 900 });
  await resize(450);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

for (const width of [390, 1440]) {
  test(`详情全屏 ${width}px 铺满页面且可退出并恢复`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/?demo=1");
    const detail = page.getByTestId("node-detail");
    const before = (await detail.boundingBox())!.width;
    await detail.getByTestId("node-body").locator("summary").click();
    await detail
      .getByRole("button", { name: "全屏展示详情", exact: true })
      .click();
    await expect(detail).toHaveAttribute("role", "dialog");
    const box = (await detail.boundingBox())!;
    expect(box.x).toBeCloseTo(0, 0);
    expect(box.y).toBeCloseTo(0, 0);
    expect(box.width).toBeCloseTo(width, 0);
    expect(box.height).toBeCloseTo(900, 0);
    await expect(detail.getByTestId("node-body")).toHaveAttribute("open", "");
    expect(
      await page.locator("header").evaluate((el) => (el as HTMLElement).inert),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(detail).toBeVisible();
    await expect(detail).not.toHaveAttribute("role", "dialog");
    expect((await detail.boundingBox())!.width).toBeCloseTo(before, 0);
    expect(
      await page.locator("header").evaluate((el) => (el as HTMLElement).inert),
    ).toBe(false);
    await expect(detail.getByTestId("node-body")).toHaveAttribute("open", "");
    await detail
      .getByRole("button", { name: "全屏展示详情", exact: true })
      .click();
    await detail
      .getByRole("button", { name: "退出详情全屏", exact: true })
      .click();
    await expect(detail).not.toHaveAttribute("role", "dialog");
  });
}

for (const width of [390, 1440]) {
  test(`教材阅读排版 ${width}px 保留正文且行长适宜`, async ({ page }) => {
    const data = structuredClone(demo) as KnowledgeMap;
    const node = data.nodes.find((n) => n.id === "overfit")!;
    node.summary = [
      "1. 要研究的量是什么",
      "设 X₁,…,Xₙ 独立同分布于 N(μ,σ²)。".repeat(8),
      "X̄=(X₁+⋯+Xₙ)/n，\nS²=Σᵢ₌₁ⁿ(Xᵢ−X̄)²/(n−1)。",
      "2. 从恒等式到分布",
      "<img src=x onerror=alert(1)>\n正态性和独立性必须分别验证。".repeat(20),
    ].join("\n\n");
    await writeFile(fixture, JSON.stringify(data));
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await page
      .getByRole("button", { name: "查看知识点：过拟合", exact: true })
      .click();
    const detail = page.getByTestId("node-detail");
    await detail
      .getByRole("button", { name: "全屏展示详情", exact: true })
      .click();
    const body = detail.getByTestId("node-body");
    await expect(body).not.toHaveAttribute("open", "");
    await body.locator("summary").click();
    const text = detail.locator("#node-summary");
    expect(await text.textContent()).toBe(node.summary);
    await expect(text.getByRole("heading")).toHaveCount(2);
    await expect(text.locator("p")).toHaveCount(3);
    await expect(text.locator("img")).toHaveCount(0);
    const box = (await text.boundingBox())!;
    expect(box.width).toBeLessThanOrEqual(780);
    expect(Math.abs(box.x + box.width / 2 - width / 2)).toBeLessThan(12);
    const typography = await text
      .locator("p")
      .first()
      .evaluate((el) => {
        const css = getComputedStyle(el);
        return {
          size: parseFloat(css.fontSize),
          color: css.color,
          background: css.backgroundColor,
        };
      });
    expect(typography.size).toBeGreaterThanOrEqual(16);
    expect(typography.color).toBe("rgb(52, 58, 52)");
    expect(typography.background).toBe("rgba(0, 0, 0, 0)");
    expect(
      await detail.evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    await detail.evaluate((el) => {
      el.scrollTop = el.scrollHeight;
    });
    const exit = detail.getByRole("button", {
      name: "退出详情全屏",
      exact: true,
    });
    const exitBox = (await exit.boundingBox())!;
    expect(exitBox.y).toBeGreaterThanOrEqual(0);
    expect(exitBox.y + exitBox.height).toBeLessThan(100);
    await exit.click();
    await expect(body).toHaveAttribute("open", "");
  });
}

for (const width of [390, 1440]) {
  test(`顶部拖动不裁切且视角不跟随 ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/?demo=1");
    await page.keyboard.press("Escape");
    const node = page.getByRole("button", {
      name: "查看知识点：过拟合",
      exact: true,
    });
    await expect(node).toBeVisible();
    await page.getByRole("button", { name: "回到全图", exact: true }).click();
    // Wait for the explicit fit-view animation before measuring the drag.
    await page.waitForTimeout(350);
    const workspace = (await page.locator("main").boundingBox())!;
    const before = (await node.boundingBox())!;
    const viewport = page.locator(".react-flow__viewport");
    const transform = await viewport.getAttribute("style");
    const target = {
      x: workspace.x + workspace.width * 0.4,
      y: workspace.y + 95,
    };
    await page.mouse.move(
      before.x + before.width / 2,
      before.y + before.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(target.x, target.y, { steps: 12 });
    await page.mouse.up();
    await expect(viewport).toHaveAttribute("style", transform!);
    const after = (await node.boundingBox())!;
    expect(after.y).toBeLessThan(workspace.y + 116);
    // Bounding boxes alone pass even when an ancestor clips the card.
    expect(
      await node.evaluate((el) => {
        const r = el.getBoundingClientRect();
        return [r.top + 2, r.bottom - 2].every((y) =>
          [r.left + 2, r.right - 2].every((x) =>
            el.contains(document.elementFromPoint(x, y)),
          ),
        );
      }),
    ).toBe(true);
    await page.screenshot({ path: `.local/top-drag-${width}.png` });
    await page
      .locator("main")
      .getByRole("button")
      .filter({ hasText: "返回我的地图" })
      .click();
    await expect(
      page.getByRole("button", { name: "查看知识点：过拟合", exact: true }),
    ).toHaveCount(0);
  });
}

test("选中节点高亮直接关联节点，关系线流动并随选择清理", async ({ page }) => {
  await page.goto("/?demo=1");
  const card = (id: string) =>
    page.locator(`.react-flow__node[data-id="${id}"] > div`);
  const related = page.locator('[class*="relatedNode"]');
  const paths = page.locator(
    ".react-flow__edge.animated .react-flow__edge-path",
  );
  await expect(related).toHaveCount(2);
  await expect(card("complexity")).toHaveClass(/relatedNode/);
  await expect(card("split")).toHaveClass(/relatedNode/);
  await expect(card("overfit")).not.toHaveClass(/relatedNode/);
  await expect(paths).toHaveCount(2);
  await expect
    .poll(() =>
      paths.first().evaluate((el) => getComputedStyle(el).animationName),
    )
    .not.toBe("none");
  const offset = await paths
    .first()
    .evaluate((el) => getComputedStyle(el).strokeDashoffset);
  await expect
    .poll(() =>
      paths.first().evaluate((el) => getComputedStyle(el).strokeDashoffset),
    )
    .not.toBe(offset);
  await expect(
    page
      .locator('.react-flow__edge[data-id^="tree-"] .react-flow__edge-path')
      .first(),
  ).toHaveCSS("animation-name", "none");

  await page
    .getByRole("button", { name: "查看知识点：模型复杂度", exact: true })
    .click();
  await expect(related).toHaveCount(1);
  await expect(card("overfit")).toHaveClass(/relatedNode/);
  await expect(card("split")).not.toHaveClass(/relatedNode/);
  await expect(paths).toHaveCount(1);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(paths).toHaveCSS("animation-name", "none");
  await expect(card("overfit")).toHaveClass(/relatedNode/);
  await page.keyboard.press("Escape");
  await expect(related).toHaveCount(0);
  await expect(paths).toHaveCount(0);
});
