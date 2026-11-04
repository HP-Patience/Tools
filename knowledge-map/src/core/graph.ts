import dagre from "@dagrejs/dagre";
import type { KnowledgeMap, KnowledgeNode } from "./types";
export function childrenByParent(nodes: KnowledgeNode[]) {
  const children = new Map<string, string[]>();
  for (const n of nodes)
    if (n.parentId)
      children.set(n.parentId, [...(children.get(n.parentId) ?? []), n.id]);
  return children;
}
export function ancestors(nodes: KnowledgeNode[], id: string): string[] {
  const index = new Map(nodes.map((n) => [n.id, n]));
  const result: string[] = [];
  const seen = new Set<string>([id]);
  let parent = index.get(id)?.parentId;
  while (parent && !seen.has(parent)) {
    result.push(parent);
    seen.add(parent);
    parent = index.get(parent)?.parentId;
  }
  return result;
}
export function visibleNodes(
  map: KnowledgeMap,
  collapsed: Set<string>,
  scope: "main" | "unassigned",
) {
  const children = childrenByParent(map.nodes);
  const index = new Map(map.nodes.map((n) => [n.id, n]));
  const visible: KnowledgeNode[] = [];
  const stack = map.nodes
    .filter((n) => n.placement === scope && n.parentId === null)
    .map((n) => n.id)
    .reverse();
  const visited = new Set<string>();
  while (stack.length) {
    const id = stack.pop()!;
    if (visited.has(id)) continue;
    visited.add(id);
    const n = index.get(id);
    if (!n) continue;
    visible.push(n);
    if (!collapsed.has(id))
      stack.push(...(children.get(id) ?? []).slice().reverse());
  }
  return visible;
}
export function layoutNodes(nodes: KnowledgeNode[]) {
  const graph = new dagre.graphlib.Graph();
  graph.setGraph({
    rankdir: "LR",
    ranksep: 92,
    nodesep: 26,
    marginx: 28,
    marginy: 28,
  });
  graph.setDefaultEdgeLabel(() => ({}));
  const ids = new Set(nodes.map((n) => n.id));
  for (const n of nodes) graph.setNode(n.id, { width: 180, height: 54 });
  for (const n of nodes)
    if (n.parentId && ids.has(n.parentId)) graph.setEdge(n.parentId, n.id);
  if (nodes.length) dagre.layout(graph);
  return new Map(
    nodes.map((n) => {
      const p = graph.node(n.id);
      return [n.id, { x: p.x - 90, y: p.y - 27 }];
    }),
  );
}
export function searchNodes(map: KnowledgeMap, query: string) {
  const text = query.trim().toLocaleLowerCase();
  if (!text) return [];
  return map.nodes
    .filter((n) =>
      [n.title, n.summary, ...n.questions.map((q) => q.text)].some((v) =>
        v.toLocaleLowerCase().includes(text),
      ),
    )
    .sort(
      (a, b) =>
        Number(b.title.toLocaleLowerCase().includes(text)) -
        Number(a.title.toLocaleLowerCase().includes(text)),
    );
}
export function changedNodeIds(previous: KnowledgeMap, current: KnowledgeMap) {
  const before = new Map(previous.nodes.map((n) => [n.id, JSON.stringify(n)]));
  return new Set(
    current.nodes
      .filter((n) => before.get(n.id) !== JSON.stringify(n))
      .map((n) => n.id),
  );
}
