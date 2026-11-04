import { describe, expect, it } from "vitest";
import demo from "../../examples/machine-learning.json";
import { parseMap, validateMap } from "../../src/core/validate";
import type { KnowledgeMap } from "../../src/core/types";
const sample = () => structuredClone(demo) as KnowledgeMap;
const invalid = (change: (m: KnowledgeMap) => void) => {
  const m = sample();
  change(m);
  expect(validateMap(m).ok).toBe(false);
};
describe("拒绝不安全或不一致的知识数据", () => {
  it("非法 JSON", () => expect(parseMap("{").ok).toBe(false));
  it("未知版本", () =>
    expect(validateMap({ ...sample(), schemaVersion: 2 }).ok).toBe(false));
  it("未知属性", () =>
    expect(validateMap({ ...sample(), password: "secret" }).ok).toBe(false));
  it("重复节点", () => invalid((m) => m.nodes.push({ ...m.nodes[0] })));
  it("重复来源", () => invalid((m) => m.sources.push({ ...m.sources[0] })));
  it("重复关联", () => invalid((m) => m.relations.push({ ...m.relations[0] })));
  it("悬空父节点", () => invalid((m) => (m.nodes[0].parentId = "missing")));
  it("父子循环", () => invalid((m) => (m.nodes[0].parentId = "overfit")));
  it("自环", () => invalid((m) => (m.nodes[0].parentId = m.nodes[0].id)));
  it("悬空来源", () => invalid((m) => (m.nodes[0].sourceIds = ["missing"])));
  it("悬空关联", () => invalid((m) => (m.relations[0].target = "missing")));
  it("关联自己", () =>
    invalid((m) => (m.relations[0].target = m.relations[0].source)));
  it("语义重复关联", () =>
    invalid((m) => m.relations.push({ ...m.relations[0], id: "different" })));
  it("待归类不能有父节点", () =>
    invalid((m) => (m.nodes[1].placement = "unassigned")));
  it("待归类不能作为父节点", () =>
    invalid((m) => (m.nodes[0].placement = "unassigned")));
  it("空白标题", () => invalid((m) => (m.nodes[0].title = "  ")));
  it("非法时间", () => invalid((m) => (m.nodes[0].updatedAt = "yesterday")));
  it("时间倒流", () =>
    invalid((m) => (m.nodes[0].updatedAt = "2000-01-01T00:00:00Z")));
  it("疑问重复 ID", () =>
    invalid((m) => {
      const n = m.nodes.find((n) => n.questions.length)!;
      n.questions.push({ ...n.questions[0] });
    }));
  for (const url of [
    "javascript:alert(1)",
    "file:///etc/passwd",
    "data:text/html,test",
    "https://user:password@example.com",
  ])
    it(`拒绝来源 ${url}`, () => invalid((m) => (m.sources[0].url = url)));
  it("允许纯文本包含 HTML 字符（渲染层必须转义）", () => {
    const m = sample();
    m.nodes[0].summary = "<script>alert(1)</script>";
    expect(validateMap(m).ok).toBe(true);
  });
});
