/*
 * HTML -> Markdown / 纯文本 转换
 * 针对轻小说网（book.novel.qq.com）返回的章节 HTML 结构。
 */
import { parse } from "node-html-parser";

/** 图片在正文中的引用路径 */
function imagePath(cid, src) {
    const filename = src.split("?")[0].split("/").pop() || `img-${Date.now()}.jpg`;
    return `images/${cid}/${filename}`;
}

/** 行内元素 -> markdown */
function inline(node) {
    let out = "";
    for (const child of node.childNodes) {
        if (child.nodeType === 3) {
            out += child.text;
            continue;
        }
        if (child.nodeType !== 1) continue;
        const tag = (child.rawTagName || "").toLowerCase();
        if (tag === "b" || tag === "strong") out += `**${inline(child)}**`;
        else if (tag === "i" || tag === "em") out += `*${inline(child)}*`;
        else if (tag === "br") out += "\n";
        else if (tag === "img") continue;
        else out += inline(child);
    }
    return out.replace(/\u00a0/g, " ").replace(/[ \t]+/g, " ").trim();
}

function headingLevel(tag, cls) {
    if (/first-title/.test(cls)) return 1;
    if (/second-title/.test(cls)) return 2;
    if (/third-title/.test(cls)) return 3;
    const m = /^h([1-6])$/.exec(tag);
    return m ? Number(m[1]) : 2;
}

/**
 * @param {string} html 章节 HTML
 * @param {{cid: number|string, mode: "markdown"|"txt"}} options
 * @returns {{ content: string, images: {src: string, path: string}[] }}
 */
export function convertChapter(html, { cid, mode }) {
    const markdown = mode === "markdown";
    const root = parse(html || "", { comment: false });
    const blocks = [];
    const images = [];

    const emitImage = (img) => {
        const src = img.getAttribute("src");
        if (!src) return;
        const path = imagePath(cid, src);
        images.push({ src, path });
        const alt = (img.getAttribute("alt") || "").trim();
        if (markdown) blocks.push(`![${alt}](${path})`);
    };

    const walk = (node) => {
        for (const child of node.childNodes) {
            if (child.nodeType === 3) {
                const t = child.text.trim();
                if (t) blocks.push(t);
                continue;
            }
            if (child.nodeType !== 1) continue;

            const tag = (child.rawTagName || "").toLowerCase();
            const cls = child.getAttribute("class") || "";

            if (tag === "img") {
                emitImage(child);
                continue;
            }

            if (/^h[1-6]$/.test(tag)) {
                const level = headingLevel(tag, cls);
                const title = inline(child);
                if (!title) {
                    // 封面这类只有图片的标题
                    const img = child.querySelector("img");
                    if (img) emitImage(img);
                    continue;
                }
                blocks.push(markdown ? `${"#".repeat(level)} ${title}` : title);
                continue;
            }

            if (tag === "p") {
                const text = inline(child);
                if (!text) continue;
                if (!markdown) {
                    blocks.push(text);
                } else if (/yinwen/.test(cls)) {
                    blocks.push(`> ${text}`);
                } else if (/tushuo/.test(cls)) {
                    blocks.push(`*${text}*`);
                } else {
                    blocks.push(text);
                }
                continue;
            }

            // div 等容器：继续下钻（图片、图注按文档顺序输出）
            walk(child);
        }
    };

    walk(root);

    return { content: blocks.join("\n\n") + "\n", images };
}
