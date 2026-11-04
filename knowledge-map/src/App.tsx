import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import {
  AlertCircle,
  ArrowLeft,
  ChevronRight,
  Layers,
  LockKeyhole,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Network,
  Search,
  X,
} from "lucide-react";
import { useKnowledgeMap } from "./useKnowledgeMap";
import { ancestors, childrenByParent, searchNodes } from "./core/graph";
import { MapCanvas } from "./components/MapCanvas";
import { NodeDetails } from "./components/NodeDetails";
import styles from "./styles/App.module.css";
import { DEFAULT_MAP_ID, MAP_OPTIONS } from "./mapCatalog";
export default function App() {
  const initialParams = new URLSearchParams(location.search);
  const [mapId, setMapId] = useState(
    initialParams.get("map") ?? DEFAULT_MAP_ID,
  );
  const [demo, setDemo] = useState(initialParams.get("demo") === "1");
  const [focusMode, setFocusMode] = useState(false);
  const { map, error, loading, changed, changeNote, reload } = useKnowledgeMap(
    mapId,
    demo,
  );
  const [selected, setSelected] = useState<string | null>(
    demo ? "overfit" : null,
  );
  const [collapsed, setCollapsed] = useState(new Set<string>());
  const [scope, setScope] = useState<"main" | "unassigned">("main");
  const [focus, setFocus] = useState<{ id: string; token: number } | null>(
    null,
  );
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [detailWidth, setDetailWidth] = useState(326);
  const expandSidebarRef = useRef<HTMLButtonElement>(null);
  const collapseSidebarRef = useRef<HTMLButtonElement>(null);
  const toggleSidebar = (collapse: boolean) => {
    setSidebarCollapsed(collapse);
    requestAnimationFrame(() =>
      (collapse ? expandSidebarRef : collapseSidebarRef).current?.focus(),
    );
  };
  const searchRef = useRef<HTMLInputElement>(null);
  const searchArea = useRef<HTMLDivElement>(null);
  const token = useRef(0);
  const closeDetails = useCallback(() => {
    setSelected(null);
  }, []);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
      if (e.key === "Escape") {
        if (focusMode) {
          setFocusMode(false);
          return;
        }
        setSearchOpen(false);
        setNavOpen(false);
        closeDetails();
      }
    };
    const outside = (e: PointerEvent) => {
      if (!searchArea.current?.contains(e.target as Element))
        setSearchOpen(false);
    };
    window.addEventListener("keydown", key);
    document.addEventListener("pointerdown", outside);
    return () => {
      window.removeEventListener("keydown", key);
      document.removeEventListener("pointerdown", outside);
    };
  }, [closeDetails, focusMode]);
  useEffect(() => {
    if (!map) return;
    const ids = new Set(map.nodes.map((n) => n.id));
    setSelected((previous) =>
      previous && ids.has(previous) ? previous : null,
    );
    setCollapsed(
      (previous) => new Set([...previous].filter((id) => ids.has(id))),
    );
  }, [map]);
  const choose = useCallback(
    (id: string) => {
      if (!map) return;
      const node = map.nodes.find((n) => n.id === id);
      if (!node) return;
      setScope(node.placement);
      setSelected(id);
      setCollapsed((previous) => {
        const next = new Set(previous);
        for (const parent of ancestors(map.nodes, id)) next.delete(parent);
        return next;
      });
      setFocus({ id, token: ++token.current });
      setSearchOpen(false);
      setNavOpen(false);
    },
    [map],
  );
  const toggle = useCallback(
    (id: string) => {
      setCollapsed((previous) => {
        const next = new Set(previous);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
      if (map && selected && ancestors(map.nodes, selected).includes(id))
        setSelected(id);
    },
    [map, selected],
  );
  const changeMap = (nextId: string) => {
    setMapId(nextId);
    setDemo(false);
    const url = new URL(location.href);
    url.searchParams.set("map", nextId);
    url.searchParams.delete("demo");
    history.replaceState(null, "", url);
    setSelected(null);
    setCollapsed(new Set());
    setScope("main");
    setQuery("");
    setFocus(null);
    setNavOpen(false);
  };
  const changeMode = (next: boolean) => {
    setDemo(next);
    const url = new URL(location.href);
    if (next) url.searchParams.set("demo", "1");
    else {
      url.searchParams.delete("demo");
      url.searchParams.set("map", mapId);
    }
    history.replaceState(null, "", url);
    setSelected(next ? "overfit" : null);
    setCollapsed(new Set());
    setScope("main");
    setQuery("");
    setSearchOpen(false);
    setFocus(null);
    setFocusMode(false);
    setNavOpen(false);
  };
  const results = useMemo(
    () => (map ? searchNodes(map, query) : []),
    [map, query],
  );
  const selectedNode = map?.nodes.find((n) => n.id === selected);
  const childMap = useMemo(() => childrenByParent(map?.nodes ?? []), [map]);
  const roots =
    map?.nodes.filter((n) => n.parentId === null && n.placement === "main") ??
    [];
  const outline =
    roots.length === 1
      ? map!.nodes.filter((n) => n.parentId === roots[0].id)
      : roots;
  const pending =
    map?.nodes.filter((n) => n.placement === "unassigned").length ?? 0;
  const questions =
    map?.nodes.reduce(
      (sum, n) => sum + n.questions.filter((q) => q.status === "open").length,
      0,
    ) ?? 0;
  const getCount = (id: string) => {
    let count = 0;
    const stack = [id];
    while (stack.length) {
      const current = stack.pop()!;
      count++;
      stack.push(...(childMap.get(current) ?? []));
    }
    return count;
  };
  return (
    <div className={`${styles.app} ${focusMode ? styles.focusMode : ""}`}>
      <header className={styles.header}>
        {sidebarCollapsed && (
          <button
            ref={expandSidebarRef}
            className={styles.sidebarToggle}
            aria-label="展开左侧边栏"
            title="展开左侧边栏"
            aria-controls="knowledge-sidebar"
            aria-expanded={false}
            onClick={() => toggleSidebar(false)}
          >
            <PanelLeftOpen size={18} />
          </button>
        )}
        <button
          className={styles.mobileMenu}
          aria-label="打开知识导航"
          onClick={() => setNavOpen(true)}
        >
          <Menu size={19} />
        </button>
        <div className={styles.brand}>
          <span>
            <Network size={22} strokeWidth={1.5} />
          </span>
          知序
        </div>
        <div className={styles.searchArea} ref={searchArea}>
          <div className={styles.searchInput}>
            <button
              aria-label="打开搜索"
              onClick={() => searchRef.current?.focus()}
            >
              <Search size={16} />
            </button>
            <input
              ref={searchRef}
              aria-label="搜索知识点"
              placeholder="搜索知识点…"
              title="搜索知识点（Ctrl / ⌘ K）"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => setSearchOpen(true)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && results[0]) {
                  e.preventDefault();
                  choose(results[0].id);
                }
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  searchArea.current
                    ?.querySelector<HTMLButtonElement>("[data-search-result]")
                    ?.focus();
                }
              }}
            />
            {query && (
              <button
                aria-label="清空搜索"
                onClick={() => {
                  setQuery("");
                  searchRef.current?.focus();
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>
          {searchOpen && query.trim() && (
            <div className={styles.searchResults} aria-label="搜索结果">
              <div className={styles.searchCaption}>
                {results.length
                  ? `找到 ${results.length} 个知识点`
                  : "没有找到对应知识点"}
              </div>
              {results.slice(0, 30).map((n) => (
                <button
                  key={n.id}
                  data-search-result
                  onClick={() => choose(n.id)}
                >
                  <span>
                    {n.title}
                    <small>{n.summary || "暂未补充理解"}</small>
                  </span>
                  <ChevronRight size={14} />
                </button>
              ))}
              {results.length > 30 && (
                <small className={styles.searchCaption}>
                  显示前 30 项，请缩小关键词范围。
                </small>
              )}
            </div>
          )}
        </div>
        <span
          className={styles.readonly}
          role="img"
          aria-label="只读查看"
          title={
            import.meta.env.DEV ? "本地预览 · 只读查看" : "已发布 · 只读查看"
          }
        >
          <LockKeyhole size={12} />
        </span>
      </header>
      <div
        className={`${styles.layout} ${selectedNode ? styles.hasDetail : ""} ${sidebarCollapsed ? styles.sidebarCollapsed : ""}`}
        style={{ "--detail-width": `${detailWidth}px` } as CSSProperties}
      >
        {navOpen && (
          <button
            className={styles.navBackdrop}
            aria-label="关闭知识导航"
            onClick={() => setNavOpen(false)}
          />
        )}
        <aside
          id="knowledge-sidebar"
          className={`${styles.sidebar} ${navOpen ? styles.navOpen : ""}`}
        >
          <div className={styles.sidebarTop}>
            <button
              ref={collapseSidebarRef}
              className={styles.sidebarToggle}
              aria-label="收起左侧边栏"
              title="收起左侧边栏"
              aria-controls="knowledge-sidebar"
              aria-expanded={true}
              onClick={() => toggleSidebar(true)}
            >
              <PanelLeftClose size={18} />
            </button>
            <button aria-label="关闭导航" onClick={() => setNavOpen(false)}>
              <X size={16} />
            </button>
          </div>
          <select
            className={styles.mapSelector}
            aria-label="切换知识地图"
            value={demo ? "__demo__" : mapId}
            onChange={(e) =>
              e.target.value === "__demo__"
                ? changeMode(true)
                : changeMap(e.target.value)
            }
          >
            <optgroup label="我的知识地图">
              {MAP_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.title}
                </option>
              ))}
            </optgroup>
            <option value="__demo__">示例地图（独立）</option>
          </select>
          <p className={styles.sectionLabel}>知识主干</p>
          <nav aria-label="知识主干">
            <button
              className={!selected && scope === "main" ? styles.active : ""}
              onClick={() => {
                setScope("main");
                setSelected(null);
                setCollapsed(new Set());
                setNavOpen(false);
              }}
            >
              <Network size={14} />
              <span>全部知识</span>
              <small>{(map?.nodes.length ?? 0) - pending}</small>
            </button>
            {outline.map((n) => (
              <button
                key={n.id}
                className={
                  selected &&
                  (selected === n.id ||
                    (map && ancestors(map.nodes, selected).includes(n.id)))
                    ? styles.active
                    : ""
                }
                onClick={() => choose(n.id)}
              >
                <ChevronRight size={13} />
                <span>{n.title}</span>
                <small>{getCount(n.id)}</small>
              </button>
            ))}
          </nav>
          <button
            className={`${styles.pending} ${scope === "unassigned" ? styles.active : ""}`}
            onClick={() => {
              setScope("unassigned");
              setSelected(null);
              setNavOpen(false);
            }}
          >
            <Layers size={14} />
            <span>待归类</span>
            <small>{pending}</small>
          </button>
          <button
            className={styles.demoSwitch}
            onClick={() => changeMode(!demo)}
          >
            {demo ? <ArrowLeft size={13} /> : <Network size={13} />}{" "}
            {demo ? "返回我的地图" : "查看示例地图"}
          </button>
        </aside>
        <main className={styles.workspace}>
          <div className={styles.workspaceHeading}>
            <div>
              <h1>
                {scope === "unassigned"
                  ? "待归类"
                  : (map?.title ?? "我的知识地图")}
              </h1>
              <p>
                {map?.nodes.length ?? 0} 个知识点 <span>·</span> {questions}{" "}
                个待解疑问
                {demo && (
                  <>
                    <span>·</span>不代表你的学习记录
                  </>
                )}
              </p>
            </div>
            {demo && (
              <button
                className={styles.backButton}
                onClick={() => changeMode(false)}
              >
                <ArrowLeft size={13} />
                <span>返回我的地图</span>
              </button>
            )}
          </div>
          {error && (
            <div className={styles.errorBanner} role="alert">
              <AlertCircle size={17} />
              <div>
                <strong>
                  {map
                    ? "知识文件有误，已保留上一份有效地图"
                    : "无法加载知识地图"}
                </strong>
                <pre>{error}</pre>
              </div>
              <button onClick={reload}>重试</button>
            </div>
          )}
          {loading && !map ? (
            <div className={styles.loading} role="status">
              正在展开你的知识地图…
            </div>
          ) : map ? (
            <MapCanvas
              map={map}
              collapsed={collapsed}
              scope={scope}
              selected={selected}
              changed={changed}
              focus={focus}
              onSelect={choose}
              onToggle={toggle}
              onViewExample={() => changeMode(true)}
              focusMode={focusMode}
              onToggleFocus={() => setFocusMode((value) => !value)}
              hasDetail={!!selectedNode}
            />
          ) : (
            <div className={styles.loading}>
              <AlertCircle size={26} />
              <h2>先修复数据，再继续查看</h2>
              <p>请让电脑上的 Agent 检查知识文件，并运行校验命令。</p>
              <code>npm run validate</code>
              <button className={styles.primaryButton} onClick={reload}>
                重新加载
              </button>
            </div>
          )}
          {changeNote && !error && (
            <div className={styles.changeNotice} role="status">
              {changeNote}
            </div>
          )}
        </main>
        {!focusMode && map && selectedNode && (
          <NodeDetails
            node={selectedNode}
            map={map}
            onClose={closeDetails}
            onSelect={choose}
            onResize={setDetailWidth}
            demo={demo}
          />
        )}
      </div>
    </div>
  );
}
