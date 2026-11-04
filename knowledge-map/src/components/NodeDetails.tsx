import {
  ArrowUpRight,
  BookOpen,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  MessageCircleQuestion,
  Maximize2,
  Minimize2,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { KnowledgeMap, KnowledgeNode } from "../core/types";
import styles from "../styles/App.module.css";
import { ReadingBody } from "./ReadingBody";
const kinds = {
  book: "教材",
  course: "课程",
  article: "文章",
  practice: "实践",
  conversation: "对话",
  other: "其他",
};
export function NodeDetails({
  node,
  map,
  onClose,
  onSelect,
  demo,
  onResize,
}: {
  node: KnowledgeNode;
  map: KnowledgeMap;
  onClose: () => void;
  onSelect: (id: string) => void;
  demo: boolean;
  onResize: (width: number) => void;
}) {
  const panelRef = useRef<HTMLElement>(null);
  const fullscreenButton = useRef<HTMLButtonElement>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  const [originalExpanded, setOriginalExpanded] = useState(false);
  const [selfTestOpen, setSelfTestOpen] = useState(false);
  const [answerShown, setAnswerShown] = useState(false);
  const resizeStart = useRef<{ x: number; width: number } | null>(null);
  const handleResizeStart = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || fullscreen) return;
    event.preventDefault();
    resizeStart.current = {
      x: event.clientX,
      width:
        event.currentTarget.parentElement?.getBoundingClientRect().width ?? 326,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const handleResizeMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!resizeStart.current) return;
    const next = Math.round(
      Math.max(
        0,
        resizeStart.current.width - (event.clientX - resizeStart.current.x),
      ),
    );
    onResize(next);
  };
  const handleResizeEnd = () => {
    resizeStart.current = null;
  };
  useEffect(() => {
    setExpanded(false);
    setMoreOpen(false);
    setSummaryExpanded(false);
    setOriginalExpanded(false);
    setSelfTestOpen(false);
    setAnswerShown(false);
  }, [node.id, map.id]);
  useEffect(() => {
    if (!fullscreen || !panelRef.current) return;
    const panel = panelRef.current;
    const layout = panel.parentElement!;
    const background = [
      ...Array.from(layout.children).filter((el) => el !== panel),
      ...Array.from(layout.parentElement!.children).filter(
        (el) => el !== layout,
      ),
    ].filter((el): el is HTMLElement => el instanceof HTMLElement);
    const previous = background.map((el) => el.inert);
    background.forEach((el) => {
      el.inert = true;
    });
    fullscreenButton.current?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopImmediatePropagation();
        setFullscreen(false);
      }
      if (event.key === "Tab") {
        const items = Array.from(
          panel.querySelectorAll<HTMLElement>(
            "button, summary, a[href], [tabindex='0']",
          ),
        ).filter((el) => el.getClientRects().length > 0);
        const first = items[0],
          last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", key, true);
    return () => {
      document.removeEventListener("keydown", key, true);
      background.forEach((el, i) => {
        el.inert = previous[i];
      });
      fullscreenButton.current?.focus();
    };
  }, [fullscreen]);
  const parent = map.nodes.find((n) => n.id === node.parentId);
  const relations = map.relations.filter(
    (r) => r.source === node.id || r.target === node.id,
  );
  const sources = map.sources.filter((s) => node.sourceIds.includes(s.id));
  const open = node.questions.filter((q) => q.status === "open").length;
  const testQuestion = node.questions[0];
  return (
    <aside
      ref={panelRef}
      className={`${styles.detail} ${expanded ? styles.expanded : ""} ${fullscreen ? styles.detailFullscreen : ""}`}
      role={fullscreen ? "dialog" : undefined}
      aria-modal={fullscreen || undefined}
      aria-label="知识点详情"
      data-testid="node-detail"
    >
      <div
        className={styles.detailResizeHandle}
        role="separator"
        aria-label="调整详情窗口宽度"
        aria-orientation="vertical"
        onPointerDown={handleResizeStart}
        onPointerMove={handleResizeMove}
        onPointerUp={handleResizeEnd}
        onPointerCancel={handleResizeEnd}
        onLostPointerCapture={handleResizeEnd}
      />
      <div className={styles.sheetHandle} />
      <div className={styles.detailTop}>
        <span>知识点详情</span>
        <div className={styles.detailActions}>
          <button
            className={styles.selfTestButton}
            aria-label="开始自测"
            onClick={() => {
              setSelfTestOpen(true);
              setAnswerShown(false);
            }}
          >
            自测
          </button>
          <button
            ref={fullscreenButton}
            aria-label={fullscreen ? "退出详情全屏" : "全屏展示详情"}
            title={fullscreen ? "退出全屏（Esc）" : "全屏展示详情"}
            onClick={() => setFullscreen((value) => !value)}
          >
            {fullscreen ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
          </button>
          <button
            className={styles.mobileExpand}
            aria-label={expanded ? "收起详情" : "展开详情"}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          </button>
          <button aria-label="关闭节点详情" onClick={onClose}>
            <X size={17} />
          </button>
        </div>
      </div>
      <article className={styles.readingContent}>
        <div className={styles.breadcrumb}>
          {map.title} {parent && ` / ${parent.title}`}
          {node.placement === "unassigned" && " / 待归类"}
        </div>
        <h2>{node.title}</h2>
        <div className={styles.tags}>
          <span
            className={
              node.provenance === "suggestion"
                ? styles.suggestionTag
                : styles.tag
            }
          >
            {node.provenance === "user"
              ? "我的表达"
              : node.provenance === "material"
                ? "材料整理"
                : "AI 建议 · 待确认"}
          </span>
          {open > 0 && (
            <span className={styles.questionTag}>{open} 个疑问</span>
          )}
          {demo && <span className={styles.neutralTag}>示例</span>}
        </div>
        {selfTestOpen && (
          <section className={styles.selfTest} aria-label="自测模式" data-testid="self-test">
            <div className={styles.selfTestHeader}>
              <h3>自测</h3>
              <button onClick={() => setSelfTestOpen(false)} aria-label="关闭自测">×</button>
            </div>
            <p>{testQuestion?.text || "请先合上正文，试着用自己的话说明这个知识点的核心结论、成立条件和一个例子。"}</p>
            {answerShown ? (
              <div className={styles.selfTestAnswer}>
                <strong>核对正文</strong>
                <ReadingBody text={node.summary || "暂时还没有正文。"} />
              </div>
            ) : (
              <button className={styles.selfTestReveal} onClick={() => setAnswerShown(true)}>查看正文核对</button>
            )}
          </section>
        )}
        <section className={styles.overviewSection} data-testid="node-overview">
          <h3>一段话描述</h3>
          <p className={styles.quote}>
            {node.overview || "先留一个位置，还没有补充一段话描述。"}
          </p>
        </section>
        <details
          className={styles.understanding}
          data-testid="node-body"
          open={summaryExpanded}
          onToggle={(event) => setSummaryExpanded(event.currentTarget.open)}
        >
          <summary className={styles.understandingSummary}>
            <span>正文</span>
            <span className={styles.summaryToggle}>
              {summaryExpanded ? "收起正文" : "展开正文"}
              {summaryExpanded ? (
                <ChevronUp size={14} />
              ) : (
                <ChevronDown size={14} />
              )}
            </span>
          </summary>
          <div className={styles.understandingContent}>
            <ReadingBody
              text={node.summary || "先留一个位置，还没有补充详细内容。"}
            />
          </div>
        </details>
        {node.originalExpression && (
          <details
            className={styles.understanding}
            data-testid="node-original"
            open={originalExpanded}
            onToggle={(event) => setOriginalExpanded(event.currentTarget.open)}
          >
            <summary className={styles.understandingSummary}>
              <span>原始表达</span>
              <span className={styles.summaryToggle}>
                {originalExpanded ? "收起原话" : "展开原话"}
                {originalExpanded ? (
                  <ChevronUp size={14} />
                ) : (
                  <ChevronDown size={14} />
                )}
              </span>
            </summary>
            <div className={styles.understandingContent}>
              <p className={styles.quote}>{node.originalExpression}</p>
            </div>
          </details>
        )}
        <div className={styles.mobileSummary}>
          <span>
            {open} 个待解疑问 · {relations.length} 个关联
          </span>
          <button
            onClick={() => {
              setExpanded(true);
            }}
          >
            展开详情 <ArrowUpRight size={13} />
          </button>
        </div>
        <details
          className={styles.detailExtra}
          open={moreOpen}
          onToggle={(event) => setMoreOpen(event.currentTarget.open)}
        >
          <summary>更多内容</summary>
          <div className={styles.detailExtraContent}>
            <section>
              <h3>还没弄懂</h3>
              {node.questions.length ? (
                node.questions.map((q) => (
                  <div
                    key={q.id}
                    className={`${styles.questionBox} ${q.status === "resolved" ? styles.resolved : ""}`}
                  >
                    <p>
                      <MessageCircleQuestion size={14} />
                      {q.text}
                    </p>
                    <small>
                      {q.status === "open"
                        ? "先记下来，下次继续理解。"
                        : "已记录解决 · 不等同于掌握度评分"}
                    </small>
                  </div>
                ))
              ) : (
                <p className={styles.muted}>暂未记录疑问，不代表已经掌握。</p>
              )}
            </section>
            <section>
              <h3>与已有知识的联系</h3>
              {relations.length ? (
                relations.map((r) => {
                  const other = map.nodes.find(
                    (n) =>
                      n.id === (r.source === node.id ? r.target : r.source),
                  )!;
                  return (
                    <div key={r.id} className={styles.relationItem}>
                      <button onClick={() => onSelect(other.id)}>
                        <span>{other.title}</span>
                        <small>
                          {r.label}
                          {r.status === "suggested" ? " · 建议" : ""}
                        </small>
                        <ArrowUpRight size={13} />
                      </button>
                      {r.description && <p>{r.description}</p>}
                    </div>
                  );
                })
              ) : (
                <p className={styles.muted}>暂未建立跨节点关系。</p>
              )}
            </section>
            <section>
              <h3>
                学习来源{" "}
                <small>{sources.length ? `${sources.length} 个` : ""}</small>
              </h3>
              {sources.length ? (
                sources.map((s) => (
                  <div className={styles.source} key={s.id}>
                    <BookOpen size={18} />
                    <div>
                      {s.url ? (
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {s.title}
                          <ExternalLink size={11} />
                        </a>
                      ) : (
                        <strong>{s.title}</strong>
                      )}
                      <small>
                        {kinds[s.kind]}
                        {s.locator ? ` · ${s.locator}` : ""}
                      </small>
                    </div>
                  </div>
                ))
              ) : (
                <p className={styles.muted}>来源可选，不必为了记录而填表。</p>
              )}
            </section>
            <footer className={styles.detailFooter}>
              记录于 {new Date(node.createdAt).toLocaleDateString("zh-CN")}
              <br />
              本地整理，结构由我决定。
              {demo && (
                <>
                  <br />
                  此处为演示内容，不是你的学习记录。
                </>
              )}
            </footer>
          </div>
        </details>
      </article>
    </aside>
  );
}
