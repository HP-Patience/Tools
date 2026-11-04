import check from "../generated/map-validator.js";
import type { KnowledgeMap } from "./types.ts";
export type ValidationResult =
  { ok: true; data: KnowledgeMap } | { ok: false; errors: string[] };
export function validateMap(value: unknown): ValidationResult {
  if (!check(value))
    return {
      ok: false,
      errors: (check.errors ?? [])
        .slice(0, 30)
        .map(
          (e) =>
            `${e.instancePath || "/"} ${e.message}${e.params.missingProperty ? `: ${e.params.missingProperty}` : ""}`,
        ),
    };
  const errors: string[] = [];
  function unique(items: { id: string }[], label: string) {
    const seen = new Set<string>();
    for (const item of items) {
      if (seen.has(item.id)) errors.push(`${label} ID 重复: ${item.id}`);
      seen.add(item.id);
    }
  }
  unique(value.nodes, "节点");
  unique(value.relations, "关联");
  unique(value.sources, "来源");
  const nodes = new Map(value.nodes.map((n) => [n.id, n]));
  const sources = new Set(value.sources.map((s) => s.id));
  for (const node of value.nodes) {
    if (!node.title.trim()) errors.push(`节点 ${node.id}: 标题不能为空白`);
    if (node.placement === "unassigned" && node.parentId !== null)
      errors.push(`待归类节点 ${node.id} 不能有父节点`);
    if (node.parentId !== null) {
      const parent = nodes.get(node.parentId);
      if (!parent)
        errors.push(`节点 ${node.id}: 父节点不存在 ${node.parentId}`);
      else if (parent.placement === "unassigned")
        errors.push(`节点 ${node.id}: 待归类节点不能作为父节点`);
    }
    unique(node.questions, `节点 ${node.id} 的疑问`);
    for (const source of node.sourceIds)
      if (!sources.has(source))
        errors.push(`节点 ${node.id}: 来源不存在 ${source}`);
    if (Date.parse(node.updatedAt) < Date.parse(node.createdAt))
      errors.push(`节点 ${node.id}: 更新时间早于创建时间`);
  }
  // Iterative traversal avoids stack overflow for deep maps.
  const done = new Set<string>();
  for (const node of value.nodes) {
    let id: string | null = node.id;
    const path = new Set<string>();
    while (id && nodes.has(id) && !done.has(id)) {
      if (path.has(id)) {
        errors.push(`父子关系成环: ${[...path, id].join(" → ")}`);
        break;
      }
      path.add(id);
      id = nodes.get(id)!.parentId;
    }
    for (const visited of path) done.add(visited);
  }
  const relationPairs = new Set<string>();
  for (const r of value.relations) {
    if (!nodes.has(r.source) || !nodes.has(r.target))
      errors.push(`关联 ${r.id}: 引用了不存在的节点`);
    if (r.source === r.target) errors.push(`关联 ${r.id}: 不允许关联自己`);
    const pair = `${r.source}|${r.target}|${r.label}`;
    if (relationPairs.has(pair)) errors.push(`关联 ${r.id}: 关系重复`);
    relationPairs.add(pair);
  }
  for (const source of value.sources)
    if (source.url) {
      try {
        const url = new URL(source.url);
        if (
          !["http:", "https:"].includes(url.protocol) ||
          url.username ||
          url.password
        )
          errors.push(`来源 ${source.id}: 只允许不含凭据的 HTTP(S) 链接`);
      } catch {
        errors.push(`来源 ${source.id}: URL 无效`);
      }
    }
  if (!value.title.trim()) errors.push("地图标题不能为空白");
  return errors.length
    ? { ok: false, errors: errors.slice(0, 30) }
    : { ok: true, data: value };
}
export function parseMap(text: string): ValidationResult {
  try {
    return validateMap(JSON.parse(text.replace(/^\uFEFF/, "")));
  } catch {
    return { ok: false, errors: ["JSON 解析失败：请检查引号、逗号和括号。"] };
  }
}
