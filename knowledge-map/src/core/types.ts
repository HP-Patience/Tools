export interface Question {
  id: string;
  text: string;
  status: "open" | "resolved";
}
export interface KnowledgeNode {
  id: string;
  title: string;
  parentId: string | null;
  placement: "main" | "unassigned";
  summary: string;
  overview?: string;
  originalExpression?: string;
  provenance: "user" | "material" | "suggestion";
  questions: Question[];
  sourceIds: string[];
  createdAt: string;
  updatedAt: string;
}
export interface KnowledgeSource {
  id: string;
  title: string;
  kind: "book" | "course" | "article" | "practice" | "conversation" | "other";
  url?: string;
  locator?: string;
}
export interface Relation {
  id: string;
  source: string;
  target: string;
  label: string;
  description?: string;
  status: "confirmed" | "suggested";
}
export interface KnowledgeMap {
  schemaVersion: 1;
  id: string;
  title: string;
  description: string;
  updatedAt: string;
  nodes: KnowledgeNode[];
  relations: Relation[];
  sources: KnowledgeSource[];
}
export interface ReleaseInfo {
  version: string;
  builtAt: string;
  sourceHash: string;
  mapHash: string;
}
