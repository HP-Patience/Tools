#!/usr/bin/env node
/*
 * 用无头 Edge 把 HTML 打印成 PDF（A4、保留背景、按章节分页）。
 * 用法：node tools/build_pdf.js <input.html> <output.pdf>
 */
import path from "node:path";
import { pathToFileURL } from "node:url";
import { launchBrowser } from "../src/browser.js";

const input = process.argv[2];
const output = process.argv[3];

if (!input || !output) {
    console.error("用法：node tools/build_pdf.js <input.html> <output.pdf>");
    process.exit(1);
}

const { browser, close } = await launchBrowser({ headless: true });
try {
    const page = await browser.newPage();
    const url = pathToFileURL(path.resolve(input)).href;
    await page.goto(url, { waitUntil: "networkidle2", timeout: 120000 });
    // 等图片解码完成，避免 PDF 里出现空框
    await page.evaluate(async () => {
        await Promise.all(
            [...document.images]
                .filter((img) => !img.complete)
                .map((img) => new Promise((resolve) => {
                    img.addEventListener("load", resolve, { once: true });
                    img.addEventListener("error", resolve, { once: true });
                }))
        );
        if (document.fonts?.ready) await document.fonts.ready;
    });

    await page.pdf({
        path: path.resolve(output),
        printBackground: true,
        preferCSSPageSize: true,
        outline: true,
    });
    console.log(`PDF: ${path.resolve(output)}`);
} finally {
    await close();
}
