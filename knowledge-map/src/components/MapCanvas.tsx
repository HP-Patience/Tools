import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Handle,
  Position,
  useReactFlow,
  useNodesInitialized,
  type Node,
  type NodeProps,
  type Edge,
  type NodeChange,
} from "@xyflow/react";
import {
  ChevronDown,
  ChevronRight,
  Maximize2,
  Minimize2,
  Minus,
  Plus,
  Network,
} from "lucide-react";
import { childrenByParent, layoutNodes, visibleNodes } from "../core/graph";
import type { KnowledgeMap, KnowledgeNode } from "../core/types";
import styles from "../styles/App.module.css";
type AtlasNode = Node<
  {
    item: KnowledgeNode;
    childCount: number;
    collapsed: boolean;
    selected: boolean;
    related: boolean;
    changed: boolean;
    select: (id: string) => void;
    toggle: (id: string) => void;
  },
  "knowledge"
>;
const KnowledgeCard = memo(function KnowledgeCard({
  data,
}: NodeProps<AtlasNode>) {
  const n = data.item;
  const questions = n.questions.filter((q) => q.status === "open").length;
  return (
    <div
      className={[
        styles.node,
        n.parentId === null && n.placement === "main" ? styles.rootNode : "",
        data.selected ? styles.selectedNode : "",
        data.related ? styles.relatedNode : "",
        data.changed ? styles.changedNode : "",
        n.provenance === "suggestion" ? styles.suggestedNode : "",
      ].join(" ")}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <button
        className={`${styles.nodeButton} nopan`}
        onClick={() => data.select(n.id)}
        aria-label={`查看知识点：${n.title}`}
        aria-pressed={data.selected}
        title={n.title}
      >
        <span className={styles.nodeTitle}>{n.title}</span>
        {questions > 0 && (
          <span
            className={styles.questionDot}
            aria-label={`${questions} 个待解疑问`}
          />
        )}
      </button>
      {data.childCount > 0 && (
        <button
          className={`${styles.collapse} nodrag nopan`}
          onClick={() => data.toggle(n.id)}
          aria-label={`${data.collapsed ? "展开" : "折叠"}${n.title}`}
          aria-expanded={!data.collapsed}
        >
          {data.collapsed ? (
            <ChevronRight size={12} />
          ) : (
            <ChevronDown size={12} />
          )}
          <small>{data.childCount}</small>
        </button>
      )}
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
});
const nodeTypes = { knowledge: KnowledgeCard };
interface Props {
  map: KnowledgeMap;
  collapsed: Set<string>;
  scope: "main" | "unassigned";
  selected: string | null;
  changed: Set<string>;
  focus: { id: string; token: number } | null;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
  onViewExample: () => void;
  hasDetail: boolean;
  focusMode: boolean;
  onToggleFocus: () => void;
}
function Canvas(props: Props) {
  const {
    map,
    collapsed,
    scope,
    selected,
    changed,
    focus,
    onSelect,
    onToggle,
    focusMode,
    onToggleFocus,
  } = props;
  // Keep renderer-only layout state local; never write positions to knowledge data.
  const [measurements, setMeasurements] = useState<
    Record<string, { width: number; height: number }>
  >({});
  const [draggedPositions, setDraggedPositions] = useState<
    Record<string, { x: number; y: number }>
  >({});
  const onNodesChange = useCallback((changes: NodeChange<AtlasNode>[]) => {
    setMeasurements((previous) => {
      let next = previous;
      for (const change of changes) {
        if (change.type !== "dimensions" || !change.dimensions) continue;
        const { width, height } = change.dimensions;
        if (
          previous[change.id]?.width === width &&
          previous[change.id]?.height === height
        )
          continue;
        if (next === previous) next = { ...previous };
        next[change.id] = { width, height };
      }
      return next;
    });
    setDraggedPositions((previous) => {
      let next = previous;
      for (const change of changes) {
        if (change.type !== "position" || !change.position) continue;
        const { x, y } = change.position;
        if (previous[change.id]?.x === x && previous[change.id]?.y === y)
          continue;
        if (next === previous) next = { ...previous };
        next[change.id] = { x, y };
      }
      return next;
    });
  }, []);
  const visible = useMemo(
    () => visibleNodes(map, collapsed, scope),
    [map, collapsed, scope],
  );
  const layoutPositions = useMemo(() => layoutNodes(visible), [visible]);
  const positions = useMemo(() => {
    const next = new Map(layoutPositions);
    for (const [id, position] of Object.entries(draggedPositions))
      next.set(id, position);
    return next;
  }, [layoutPositions, draggedPositions]);
  const children = useMemo(() => childrenByParent(map.nodes), [map]);
  const selectedRelations = useMemo(() => {
    const ids = new Set(visible.map((n) => n.id));
    return map.relations.filter(
      (r) =>
        (r.source === selected || r.target === selected) &&
        ids.has(r.source) &&
        ids.has(r.target),
    );
  }, [visible, map.relations, selected]);
  const relatedIds = useMemo(
    () => new Set(selectedRelations.flatMap((r) => [r.source, r.target])),
    [selectedRelations],
  );
  const nodes: AtlasNode[] = useMemo(
    () =>
      visible.map((item) => ({
        id: item.id,
        type: "knowledge",
        position: positions.get(item.id)!,
        width: 180,
        height: 54,
        measured: measurements[item.id],
        draggable: true,
        selectable: false,
        data: {
          item,
          childCount: children.get(item.id)?.length ?? 0,
          collapsed: collapsed.has(item.id),
          selected: selected === item.id,
          related: selected !== item.id && relatedIds.has(item.id),
          changed: changed.has(item.id),
          select: onSelect,
          toggle: onToggle,
        },
      })),
    [
      visible,
      measurements,
      positions,
      children,
      collapsed,
      selected,
      relatedIds,
      changed,
      onSelect,
      onToggle,
      focusMode,
      onToggleFocus,
    ],
  );
  const edges: Edge[] = useMemo(() => {
    const ids = new Set(visible.map((n) => n.id));
    const parents: Edge[] = visible
      .filter((n) => n.parentId && ids.has(n.parentId))
      .map((n) => ({
        id: `tree-${n.id}`,
        source: n.parentId!,
        target: n.id,
        type: "default",
        selectable: false,
        focusable: false,
        style: { stroke: "#bacbb0", strokeWidth: 1.4 },
      }));
    const related: Edge[] = selectedRelations.map((r) => ({
      id: `relation-${r.id}`,
      animated: true,
      className: styles.relatedEdge,
      source: r.source,
      target: r.target,
      type: "default",
      selectable: false,
      focusable: false,
      style: { stroke: "#a77c30", strokeWidth: 2, strokeDasharray: "5 5" },
      zIndex: -1,
    }));
    return [...parents, ...related];
  }, [visible, selectedRelations]);
  const flow = useReactFlow<AtlasNode>();
  const ready = useNodesInitialized();
  const positionsRef = useRef(positions);
  positionsRef.current = positions;
  const initial = useRef("");
  useEffect(() => {
    if (!ready || !nodes.length) return;
    const key = map.id + "-" + scope;
    if (initial.current !== key) {
      initial.current = key;
      const target =
        selected && window.innerWidth < 701
          ? nodes.filter(
              (n) =>
                n.id === selected ||
                n.id === map.nodes.find((v) => v.id === selected)?.parentId,
            )
          : undefined;
      void flow.fitView({
        nodes: target,
        padding: 0.22,
        duration: 0,
        maxZoom: 1.1,
      });
    }
  }, [ready, flow, map.id, scope, nodes, selected, map.nodes]);
  useEffect(() => {
    if (!ready || !focus) return;
    const point = positionsRef.current.get(focus.id);
    if (!point) return;
    void flow.setCenter(point.x + 90, point.y + 27, {
      zoom: window.innerWidth < 701 ? 0.95 : 1.1,
      duration: 240,
    });
  }, [focus, ready, flow]);
  return (
    <>
      <div className={styles.canvas} data-testid="map-canvas">
        {nodes.length ? (
          <ReactFlow<AtlasNode>
            nodes={nodes}
            onNodesChange={onNodesChange}
            edges={edges}
            nodeTypes={nodeTypes}
            nodesDraggable
            nodesConnectable={false}
            nodesFocusable={false}
            edgesFocusable={false}
            elementsSelectable={false}
            deleteKeyCode={null}
            selectionKeyCode={null}
            minZoom={0.1}
            maxZoom={2.2}
            fitView
            panOnDrag
            autoPanOnNodeDrag={false}
            zoomOnPinch
            zoomOnDoubleClick={false}
            preventScrolling
            aria-label="只读知识地图，可拖动和缩放"
          />
        ) : (
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>
              <Network size={31} strokeWidth={1.2} />
            </div>
            <h2>
              {scope === "unassigned"
                ? "这里暂时没有待归类的知识"
                : "你的知识地图，从这里开始"}
            </h2>
            {scope === "main" && (
              <>
                <code>先阅读 AGENTS.md，再帮我整理今天所学。</code>
                <button
                  className={styles.primaryButton}
                  onClick={props.onViewExample}
                >
                  先看看示例地图 <ChevronRight size={15} />
                </button>
                <small>示例不会写入你的知识文件</small>
              </>
            )}
          </div>
        )}
      </div>
      <div className={styles.canvasFooter}>
        <button
          className={styles.focusButton}
          onClick={onToggleFocus}
          aria-label={focusMode ? "退出专注画布" : "进入专注画布"}
        >
          {focusMode ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          <span>{focusMode ? "退出专注" : "专注画布"}</span>
        </button>
        <div className={styles.legend}>
          <span>
            <i />
            待解疑问
          </span>
          <span>
            <b />
            知识关联
          </span>
        </div>
        {nodes.length > 0 && (
          <div className={styles.controls}>
            <button
              aria-label="缩小地图"
              onClick={() => void flow.zoomOut({ duration: 150 })}
            >
              <Minus size={16} />
            </button>
            <button
              aria-label="放大地图"
              onClick={() => void flow.zoomIn({ duration: 150 })}
            >
              <Plus size={16} />
            </button>
            <button
              aria-label="回到全图"
              disabled={!ready}
              onClick={() =>
                void flow.fitView({
                  padding: 0.22,
                  duration: 240,
                  maxZoom: 1.1,
                })
              }
            >
              <Maximize2 size={14} />
              <span>全图</span>
            </button>
          </div>
        )}
      </div>
    </>
  );
}
export function MapCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  );
}
