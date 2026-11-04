import { useCallback, useEffect, useRef, useState } from "react";
import mapUrl from "../data/map.json?url";
import exampleUrl from "../examples/machine-learning.json?url";
import newMapUrl from "../data/maps/new-atlas.json?url";
import { MAP_OPTIONS, DEFAULT_MAP_ID } from "./mapCatalog";
import { parseMap } from "./core/validate";
import { changedNodeIds } from "./core/graph";
import type { KnowledgeMap } from "./core/types";
export function useKnowledgeMap(mapId: string, demo: boolean) {
  const [map, setMap] = useState<KnowledgeMap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [changed, setChanged] = useState(new Set<string>());
  const [changeNote, setChangeNote] = useState("");
  const [retry, setRetry] = useState(0);
  const previous = useRef<KnowledgeMap | null>(null);
  const sequence = useRef(0);
  const mode = useRef("");
  useEffect(() => {
    const key = `${demo ? "demo" : "map"}:${mapId}`;
    if (mode.current !== key) {
      mode.current = key;
      previous.current = null;
      setMap(null);
      setChanged(new Set());
      setChangeNote("");
    }
    setError(null);
    setLoading(true);
    let controller: AbortController | undefined;
    const load = async () => {
      const request = ++sequence.current;
      controller?.abort();
      controller = new AbortController();
      try {
        const option =
          MAP_OPTIONS.find((item) => item.id === mapId) ?? MAP_OPTIONS[0];
        const response = await fetch(
          demo
            ? exampleUrl
            : option.id === DEFAULT_MAP_ID && import.meta.env.DEV
              ? "/__atlas/map"
              : option.id === DEFAULT_MAP_ID
                ? mapUrl
                : newMapUrl,
          { cache: "no-store", signal: controller.signal },
        );
        const raw = await response.text();
        if (!response.ok)
          throw new Error(`读取失败（HTTP ${response.status}）`);
        const result = parseMap(raw);
        if (!result.ok) throw new Error(result.errors.join("\n"));
        if (request !== sequence.current) return;
        const before = previous.current;
        if (before) {
          const ids = changedNodeIds(before, result.data);
          const added = result.data.nodes.filter(
            (n) => !before.nodes.some((old) => old.id === n.id),
          ).length;
          const deleted = before.nodes.filter(
            (old) => !result.data.nodes.some((n) => n.id === old.id),
          ).length;
          setChanged(ids);
          setChangeNote(
            `本次更新：新增 ${added}，修改 ${Math.max(0, ids.size - added)}，移除 ${deleted} 个节点。`,
          );
        }
        previous.current = result.data;
        setMap(result.data);
        setError(null);
      } catch (cause) {
        if (request !== sequence.current || controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "无法读取知识文件");
      } finally {
        if (request === sequence.current) setLoading(false);
      }
    };
    void load();
    const refresh = () => {
      if (!demo && mapId === DEFAULT_MAP_ID) void load();
    };
    import.meta.hot?.on("atlas:update", refresh);
    return () => {
      sequence.current++;
      controller?.abort();
      import.meta.hot?.off("atlas:update", refresh);
    };
  }, [demo, mapId, retry]);
  const reload = useCallback(() => setRetry((v) => v + 1), []);
  return { map, error, loading, changed, changeNote, reload };
}
