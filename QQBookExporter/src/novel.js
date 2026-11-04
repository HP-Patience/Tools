/*
 * 轻小说网（book.novel.qq.com）导出实现
 * 纯 HTTP 接口，无需浏览器；付费章节需携带登录 Cookie。
 */
import fs from "node:fs";
import path from "node:path";
import axios from "axios";
import { convertChapter } from "./convert.js";

const BASE = "https://book.novel.qq.com";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0";
const MODE_EXT = { txt: "txt", markdown: "md" };

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

function createClient(cookie) {
    // 默认直连：系统代理（HTTP_PROXY）转发本接口时会破坏 TLS，导致 400。
    // 如确需代理，可通过环境变量 QQREAD_PROXY 指定。
    const proxy = process.env.QQREAD_PROXY
        ? { host: new URL(process.env.QQREAD_PROXY).hostname, port: Number(new URL(process.env.QQREAD_PROXY).port) || 80 }
        : false;
    return axios.create({
        baseURL: BASE,
        timeout: 30000,
        proxy,
        headers: {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": `${BASE}/`,
            ...(cookie ? { Cookie: cookie } : {}),
        },
    });
}

async function withRetry(fn, { attempts = 3, label = "请求" } = {}) {
    let lastError;
    for (let i = 1; i <= attempts; i++) {
        try {
            return await fn();
        } catch (error) {
            lastError = error;
            if (i < attempts) {
                console.warn(`  ${label}失败（${error.message}），第 ${i} 次重试…`);
                await delay(1000 * i);
            }
        }
    }
    throw lastError;
}

function sanitize(name) {
    return String(name)
        .replace(/[\\/:*?"<>|\r\n\t]/g, "_")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 80);
}

/** 合并版中把正文标题降一级，保持「书名 # / 章节 ## / 小节 ###」的层级 */
function demoteHeadings(markdown) {
    return markdown.replace(/^(#{1,5}) /gm, "#$1 ");
}

const normalizeTitle = (text) => String(text).replace(/[\s\u3000]+/g, "");

/** 正文里是否已有与章节名相同的标题（避免合并版重复标题） */
function hasHeading(markdown, title) {
    const target = normalizeTitle(title);
    return markdown
        .split("\n")
        .some((line) => {
            const match = /^#{1,6}\s+(.+)$/.exec(line.trim());
            return match ? normalizeTitle(match[1]) === target : false;
        });
}

export async function fetchBookDetail(client, bid) {
    const { data } = await withRetry(
        () => client.get("/api/book/detail", { params: { bid } }),
        { label: "获取书籍信息" }
    );
    if (data.code !== 0 || !data.data?.book) {
        throw new Error(`获取书籍信息失败：${data.msg || `code=${data.code}`}`);
    }
    return data.data.book;
}

export async function fetchChapters(client, bid) {
    const { data } = await withRetry(
        () => client.get("/api/book/chapter-list", { params: { bid } }),
        { label: "获取目录" }
    );
    if (data.code !== 0 || !data.data?.chapters) {
        throw new Error(`获取目录失败：${data.msg || `code=${data.code}`}`);
    }
    return data.data.chapters;
}

export async function fetchChapter(client, bid, cid) {
    const { data } = await withRetry(
        () => client.get("/api/book/read", {
            params: { bid, cid },
            headers: { Referer: `${BASE}/read/${bid}/${cid}` },
        }),
        { label: `获取第 ${cid} 章` }
    );
    if (data.code !== 0) {
        throw new Error(`获取第 ${cid} 章失败：${data.msg || `code=${data.code}`}`);
    }
    return data.data;
}

async function downloadImage(client, image, outputDir) {
    const target = path.join(outputDir, image.path);
    if (fs.existsSync(target)) return;
    fs.mkdirSync(path.dirname(target), { recursive: true });
    const response = await withRetry(
        () => client.get(image.src, {
            responseType: "arraybuffer",
            timeout: 60000,
            headers: { Referer: `${BASE}/` },
        }),
        { label: "图片下载" }
    );
    fs.writeFileSync(target, response.data);
}

/**
 * @param {object} options
 * @param {string} options.bid
 * @param {string} options.outputDir
 * @param {"markdown"|"txt"} options.mode
 * @param {number[]} options.ignore
 * @param {string} [options.cookie]
 * @param {boolean} options.merge
 * @param {number} options.delayMs
 */
export async function exportNovelBook({ bid, outputDir, mode, ignore, cookie = "", merge = true, delayMs = 400 }) {
    const client = createClient(cookie);
    const book = await fetchBookDetail(client, bid);
    const chapters = await fetchChapters(client, bid);

    const bookTitle = sanitize(book.title || bid);
    const rootDir = outputDir || path.join("output", `${bid}-${bookTitle}`);
    fs.mkdirSync(rootDir, { recursive: true });

    console.log(`《${book.title}》 ${book.author || ""}`);
    console.log(`共 ${chapters.length} 章 → ${path.resolve(rootDir)}`);

    const ext = MODE_EXT[mode] || "md";
    const merged = [];
    const skipped = [];
    let exported = 0;
    let images = 0;

    for (const chapter of chapters) {
        const { seq, title, free } = chapter;
        const cid = chapter.uuid ?? seq;

        if (ignore.includes(cid) || ignore.includes(seq)) {
            console.log(`跳过（忽略）: ${seq}. ${title}`);
            continue;
        }

        // 未登录时不请求付费章节，省一次无效请求
        if (!free && !cookie) {
            console.log(`跳过（付费章节，需登录 Cookie）: ${seq}. ${title}`);
            skipped.push({ seq, title, reason: "付费章节，需登录 Cookie" });
            continue;
        }

        let data;
        try {
            data = await fetchChapter(client, bid, cid);
        } catch (error) {
            console.warn(`失败: ${seq}. ${title} → ${error.message}`);
            skipped.push({ seq, title, reason: error.message });
            continue;
        }

        const raw = data.content || "";
        if (!raw.trim()) {
            let reason;
            if (!free) {
                if (!cookie) reason = "付费章节，需登录 Cookie";
                else if (data.isAuth === false) reason = "未购买本章（需购买或开通会员）";
                else reason = "正文为空，Cookie 可能已失效";
            } else {
                reason = "接口未返回正文";
            }
            console.log(`跳过（${reason}）: ${seq}. ${title}`);
            skipped.push({ seq, title, reason });
            continue;
        }

        const { content, images: chapterImages } = convertChapter(raw, { cid, mode });
        if (mode === "markdown") {
            for (const image of chapterImages) {
                try {
                    await downloadImage(client, image, rootDir);
                    images++;
                } catch (error) {
                    console.warn(`  图片下载失败 ${image.src}：${error.message}`);
                }
            }
        }

        const filename = `${String(seq).padStart(3, "0")}-${sanitize(title)}.${ext}`;
        fs.writeFileSync(path.join(rootDir, filename), content, "utf-8");
        merged.push({ seq, title, content });
        exported++;
        console.log(`已导出 ${exported}/${chapters.length}: ${filename}`);
        if (delayMs > 0) await delay(delayMs);
    }

    if (merge && merged.length) {
        const header = [
            `# ${book.title}`,
            "",
            `- 作者：${book.author || "未知"}`,
            `- 书籍 ID：${bid}`,
            `- 导出章节：${exported}/${chapters.length}`,
            "",
            book.intro ? `> ${String(book.intro).trim().replace(/\n+/g, "\n> ")}` : "",
            "",
        ].join("\n");
        const body = merged
            .map((chapter) => {
                const content = mode === "markdown" ? demoteHeadings(chapter.content) : chapter.content;
                const title = chapter.title.trim();
                const duplicated = mode === "markdown" && hasHeading(content, title);
                return duplicated ? content : `## ${title}\n\n${content}`;
            })
            .join("\n");
        fs.writeFileSync(path.join(rootDir, `${bookTitle}.${ext}`), `${header}\n${body}`, "utf-8");
        console.log(`已合并为整本：${bookTitle}.${ext}`);
    }

    return { book, rootDir, exported, total: chapters.length, skipped, images };
}
