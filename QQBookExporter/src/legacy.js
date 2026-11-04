/*
 * 旧站（book.qq.com）导出实现
 * 需要打开真实浏览器供用户登录，依赖 puppeteer-core。
 */
import fs from "node:fs";
import path from "node:path";
import axios from "axios";
import { launchBrowser, DEFAULT_EDGE } from "./browser.js";

const MODE_EXT = { txt: "txt", markdown: "md" };

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function getBookChapters(browser, bookid) {
    const page = await browser.newPage();
    await page.goto(`https://book.qq.com/book-detail/${bookid}`, { waitUntil: "networkidle2" });
    const response = await page.evaluate(async (bookid) => {
        try {
            const res = await fetch(`https://book.qq.com/api/book/detail/chapters?bid=${bookid}`);
            const data = await res.json();
            return data.data;
        } catch (error) {
            console.error("Failed to fetch chapters:", error);
            return null;
        }
    }, bookid);
    await page.close();
    return response;
}

async function getBookContentForText(page) {
    return await page.evaluate(() => {
        const pElements = document.querySelectorAll("p");
        const textContents = [];
        for (const p of pElements) {
            const pText = p.textContent;
            if (pText === "◆参考书目") return textContents.join("\n");
            textContents.push(pText);
        }
        return textContents.join("\n");
    });
}

async function getBookContentForMarkdown(page, cid, outputDir) {
    const result = await page.evaluate((cid) => {
        const container = document.getElementById("article");
        if (!container) return [];
        const elements = container.querySelectorAll("h1,p,div.bodyPic");
        const contents = [];
        for (const e of elements) {
            if (e.tagName === "P") {
                let pContent = "";
                for (const child of e.childNodes) {
                    if (child.nodeType === Node.TEXT_NODE) {
                        if (e.classList.contains("content_110") || e.classList.contains("contentCR-1") || e.classList.contains("content3_100")) {
                            pContent += `## ${child.textContent}\n`;
                        } else {
                            pContent += child.textContent;
                        }
                    } else if (child.nodeType === Node.ELEMENT_NODE) {
                        if (child.classList.contains("italic") || child.nodeName === "I" ||
                            child.nodeName === "EM" || child.style.fontStyle === "italic") {
                            pContent += `*${child.textContent}*`;
                        } else if (child.tagName.toLowerCase() === "span" && child.classList.contains("bold")) {
                            pContent += `**${child.textContent}**`;
                        } else {
                            pContent += child.textContent;
                        }
                    }
                }
                if (pContent.includes("◆参考书目")) return contents;
                contents.push({ text: pContent, image: null });
            } else if (e.tagName === "DIV" && e.className === "bodyPic") {
                const img = e.querySelector("img");
                if (!img) continue;
                const filename = img.src.split("/").pop().split("?")[0];
                const imgPath = `images/${cid}/${filename}`;
                contents.push({
                    text: `![${img.alt}](${imgPath})`,
                    image: { src: img.src, path: imgPath, dir: `images/${cid}` },
                });
            } else if (e.tagName === "H1" && e.className === "firstTitle-1") {
                contents.push({ text: `# ${e.textContent}\n`, image: null });
            } else if (e.tagName === "H1" && e.className === "secondTitle-1") {
                contents.push({ text: `## ${e.textContent}\n`, image: null });
            } else if (e.tagName === "H1" && e.className === "frontCover") {
                const img = e.querySelector("img");
                if (!img) continue;
                const filename = img.src.split("/").pop().split("?")[0];
                const imgPath = `images/${cid}/${filename}`;
                contents.push({
                    text: `![${img.alt}](${imgPath})`,
                    image: { src: img.src, path: imgPath, dir: `images/${cid}` },
                });
            }
        }
        return contents;
    }, cid);

    let text = "";
    for (const element of result) {
        if (element.image) {
            const img = element.image;
            fs.mkdirSync(path.join(outputDir, img.dir), { recursive: true });
            const response = await axios.get(img.src, {
                responseType: "arraybuffer",
                timeout: 30000,
                headers: {
                    Referer: "https://book.qq.com/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
                },
            });
            fs.writeFileSync(path.join(outputDir, img.path), response.data);
        }
        text += element.text + "\n";
    }
    return text;
}

async function loadContent(browser, bid, cid, mode, outputDir) {
    const page = await browser.newPage();
    const url = `https://book.qq.com/book-read/${bid}/${cid}`;
    await page.goto(url, { timeout: 60000 });
    console.log(`已打开页面: ${url}`);
    try {
        await page.waitForResponse(
            (response) => response.url().startsWith(url) && response.request().method() === "POST",
            { timeout: 10000 }
        );
    } catch (error) {
        if (error.name === "TimeoutError") {
            console.error("加载错误，等待2秒后尝试读取文章内容。");
            await delay(2000);
        } else {
            throw error;
        }
    }
    const content = mode === "txt"
        ? await getBookContentForText(page)
        : await getBookContentForMarkdown(page, cid, outputDir);
    await page.close();
    return content;
}

/**
 * @param {{bid: string, outputDir?: string, mode: "markdown"|"txt", ignore: number[], executablePath?: string}} options
 */
export async function exportLegacyBook({ bid, outputDir, mode, ignore, executablePath }) {
    const dir = outputDir || "output";
    fs.mkdirSync(dir, { recursive: true });

    const baseUrl = `https://book.qq.com/book-detail/${bid}`;
    const { browser, close } = await launchBrowser({
        executablePath: executablePath || DEFAULT_EDGE,
        headless: false,
    });

    const loginPage = await browser.newPage();
    await loginPage.goto(baseUrl);
    console.log(`打开书本页面：${baseUrl}，点击登录进行登录操作，然后关闭页面。`);
    await new Promise((resolve) => loginPage.on("close", resolve));
    console.log("开始下载。");

    const chapters = await getBookChapters(browser, bid);
    if (!chapters?.length) {
        await close();
        throw new Error("未获取到章节列表，请确认书籍 ID 是否正确。");
    }

    let exported = 0;
    for (const element of chapters) {
        if (ignore.includes(element.cid)) {
            console.log(`忽略章节: ${element.cid}`);
            continue;
        }
        if (element.free == 0 && element.purchased == 0) {
            console.log(`付费且未购买章节: ${element.cid}`);
        }
        const content = await loadContent(browser, bid, element.cid, mode, dir);
        const filename = `${element.cid}-${element.chapterName}.${MODE_EXT[mode]}`.replace(/[\\/]/g, "");
        fs.writeFileSync(path.join(dir, filename), `${content}\n`, "utf-8");
        exported++;
        await delay(500);
    }
    console.log(`导出完成，共 ${exported} 章。`);
    await close();
    return { exported, total: chapters.length };
}
