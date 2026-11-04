import defaultMap from "../data/map.json";
import newMap from "../data/maps/new-atlas.json";
import type { KnowledgeMap } from "./core/types";
export interface MapOption {
  id: string;
  title: string;
  description: string;
  kind: "personal" | "example";
  data?: KnowledgeMap;
}
export const MAP_OPTIONS: MapOption[] = [
  {
    id: defaultMap.id,
    title: defaultMap.title,
    description: defaultMap.description,
    kind: "personal",
    data: defaultMap as KnowledgeMap,
  },
  {
    id: newMap.id,
    title: newMap.title,
    description: newMap.description,
    kind: "personal",
    data: newMap as KnowledgeMap,
  },
];
export const DEFAULT_MAP_ID = defaultMap.id;
