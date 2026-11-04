import { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import styles from "../styles/App.module.css";

type MathSegment = { math: string; display: boolean } | { text: string };

function segments(text: string): MathSegment[] {
  const result: MathSegment[] = [];
  const pattern = /(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$[^$\n]+\$)/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > last) result.push({ text: text.slice(last, start) });
    const raw = match[0];
    const display = raw.startsWith("$$") || raw.startsWith("\\[");
    const math = display
      ? raw.slice(2, -2)
      : raw.startsWith("\\(")
        ? raw.slice(2, -2)
        : raw.slice(1, -1);
    result.push({ math, display });
    last = start + raw.length;
  }
  if (last < text.length) result.push({ text: text.slice(last) });
  return result;
}

function MathText({ text }: { text: string }) {
  const parts = useMemo(() => segments(text), [text]);
  return (
    <>
      {parts.map((part, index) =>
        "math" in part ? (
          <span
            key={index}
            className={part.display ? styles.formulaDisplay : styles.formulaInline}
            dangerouslySetInnerHTML={{
              __html: katex.renderToString(part.math, {
                displayMode: part.display,
                throwOnError: false,
                trust: false,
                strict: "warn",
              }),
            }}
          />
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </>
  );
}

/** Renders explicit LaTeX delimiters while preserving ordinary text verbatim. */
export function ReadingBody({ text }: { text: string }) {
  const blocks = text.split(/((?:\r?\n[ \t]*){2,})/);
  return (
    <div id="node-summary" className={styles.readingBody}>
      {blocks.map((block, index) => {
        if (!block.trim()) return block;
        const heading =
          /^(?:[1-9]\d*[.、．] |[一二三四五六七八九十]+、)\S[^\r\n]{0,62}$/.test(block);
        return heading ? (
          <h3 key={index}><MathText text={block} /></h3>
        ) : (
          <p key={index}><MathText text={block} /></p>
        );
      })}
    </div>
  );
}
