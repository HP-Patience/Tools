import { describe, expect, it } from "vitest";
import demo from "../../examples/machine-learning.json";
import {
  ancestors,
  changedNodeIds,
  layoutNodes,
  searchNodes,
  visibleNodes,
} from "../../src/core/graph";
import { parseMap, validateMap } from "../../src/core/validate";
import type { KnowledgeMap } from "../../src/core/types";
const sample = () => structuredClone(demo) as KnowledgeMap;
describe("技术验证：布局与数据协议", () => {
  it("示例数据有效", () => expect(validateMap(sample()).ok).toBe(true));
  it("Dagre 生成有限、互不重叠的坐标", () => {
    const positions = [...layoutNodes(sample().nodes).values()];
    expect(positions).toHaveLength(14);
    for (const p of positions)
      expect(Number.isFinite(p.x) && Number.isFinite(p.y)).toBe(true);
    for (let a = 0; a < positions.length; a++)
      for (let b = a + 1; b < positions.length; b++)
        expect(
          Math.abs(positions[a].x - positions[b].x) >= 180 ||
            Math.abs(positions[a].y - positions[b].y) >= 54,
        ).toBe(true);
  });
  it("多个根节点可布局", () => {
    const map = sample();
    map.nodes.find((n) => n.id === "evaluation")!.parentId = null;
    expect(layoutNodes(map.nodes).size).toBe(14);
  });
  it("折叠隐藏后代而保留分支自身", () => {
    const nodes = visibleNodes(sample(), new Set(["evaluation"]), "main");
    expect(nodes.some((n) => n.id === "evaluation")).toBe(true);
    expect(nodes.some((n) => n.id === "overfit")).toBe(false);
    expect(nodes).toHaveLength(12);
  });
  it("搜索隐藏节点并获得展开路径", () => {
    expect(
      searchNodes(sample(), "过拟合").some((n) => n.id === "overfit"),
    ).toBe(true);
    expect(ancestors(sample().nodes, "overfit")).toEqual(["evaluation", "ml"]);
  });
  it("无结果与空查询安全返回", () => {
    expect(searchNodes(sample(), "不存在")).toEqual([]);
    expect(searchNodes(sample(), "  ")).toEqual([]);
  });
  it("未归类节点与主图隔离", () => {
    const map = sample();
    map.nodes.push({
      ...map.nodes[0],
      id: "pending",
      parentId: null,
      placement: "unassigned",
    });
    expect(visibleNodes(map, new Set(), "unassigned").map((n) => n.id)).toEqual(
      ["pending"],
    );
  });
  it("仅标识新增与改动，不把未改节点标记为新", () => {
    const map = sample();
    map.nodes[0].summary = "new";
    expect([...changedNodeIds(sample(), map)]).toEqual(["ml"]);
  });
  it("空地图可布局", () => {
    expect(layoutNodes([]).size).toBe(0);
  });
  it("带 UTF8 BOM 的文本可读取", () =>
    expect(parseMap("\uFEFF" + JSON.stringify(sample())).ok).toBe(true));
});
