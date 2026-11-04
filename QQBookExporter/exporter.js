#!/usr/bin/env node
/*
 * @Author: aquamarine5 && aquamarine5_@outlook.com
 * Copyright (c) 2024-2025 by @aquamarine5, RC. All Rights Reversed.
 */
import fs from "node:fs";
import path from "node:path";
import { Command } from "commander";
import { exportNovelBook } from "./src/novel.js";

const VERSION = "2.0.0";

/** 解析 -x 参数：1,2,3 / 1-9 / 3 */
function parseIgnore(text) {
    const value = (text || "").trim();
    if (!value || value === "-") return [];
    if (/^\d+(,\d+)+$/.test(value)) return value.split(",").map(Number);
    if (/^\d+-\d+$/.test(value)) {
        const [start, end] = value.split("-").map(Number);
        return Array.from({ length: Math.max(0, end - start + 1) }, (_, i) => start + i);
    }
    if (/^\d+$/.test(value)) return [Number(value)];
    throw new Error(`-x/--ignore 格式错误：「${text}」，应为 1,2,3 或 1-9 或 3`);
}

/** 从 URL 或纯数字中取出 bid */
function parseBookId(input) {
    const match = /(\d{4,})/.exec(String(input));
    if (!match) throw new Error(`无法从「${input}」中解析书籍 ID`);
    return match[1];
}

function resolveCookie(cliValue) {
    if (cliValue) return cliValue;
    if (process.env.QQREAD_COOKIE) return process.env.QQREAD_COOKIE;
    const file = path.resolve(".cookie");
    if (fs.existsSync(file)) return fs.readFileSync(file, "utf-8").trim();
    return "";
}

const program = new Command();

program
    .name("QQBookExporter")
    .description("导出 QQ阅读 / 轻小说网 的书籍内容为 TXT 或 Markdown")
    .version(VERSION)
    .argument("<bookId>", "书籍 ID 或书籍详情页链接")
    .option("-x, --ignore <chapters>", "要忽略的章节，支持 1,2,3 或 1-9 区间", "")
    .option("-o, --output <directory>", "输出目录（默认 output/<bid>-<书名>）")
    .option("-m, --mode <mode>", "导出模式：txt 或 markdown", "markdown")
    .option("-s, --source <source>", "站点：novel（轻小说网，默认）或 qq（旧站，需浏览器）", "novel")
    .option("-c, --cookie <cookie>", "登录 Cookie，用于抓取付费章节（也可用环境变量 QQREAD_COOKIE 或 .cookie 文件）")
    .option("-l, --login", "先打开浏览器扫码登录并自动获取 Cookie，再继续导出")
    .option("--no-merge", "不额外生成合并版整本文件")
    .option("--delay <ms>", "章节抓取间隔（毫秒）", "400")
    .option("--edge <path>", "旧站模式下的浏览器路径")
    .action(async (bookIdInput, options) => {
        const mode = String(options.mode).toLowerCase();
        if (!["txt", "markdown"].includes(mode)) {
            console.error(`不支持的模式：${options.mode}（可选 txt / markdown）`);
            process.exitCode = 1;
            return;
        }
        const source = String(options.source).toLowerCase();
        if (!["novel", "qq"].includes(source)) {
            console.error(`不支持的站点：${options.source}（可选 novel / qq）`);
            process.exitCode = 1;
            return;
        }

        const bid = parseBookId(bookIdInput);
        const ignore = parseIgnore(options.ignore);

        try {
            if (source === "qq") {
                const { exportLegacyBook } = await import("./src/legacy.js");
                await exportLegacyBook({
                    bid,
                    outputDir: options.output,
                    mode,
                    ignore,
                    executablePath: options.edge,
                });
                return;
            }

            let cookie = resolveCookie(options.cookie);
            if (options.login) {
                const { captureCookie } = await import("./src/login.js");
                const result = await captureCookie({ executablePath: options.edge });
                cookie = result.cookie;
            }
            const result = await exportNovelBook({
                bid,
                outputDir: options.output,
                mode,
                ignore,
                cookie,
                merge: options.merge,
                delayMs: Number(options.delay) || 0,
            });

            console.log("");
            console.log(`完成：${result.exported}/${result.total} 章 → ${path.resolve(result.rootDir)}`);
            if (result.images) console.log(`图片：${result.images} 张`);
            if (result.skipped.length) {
                console.log(`未导出 ${result.skipped.length} 章：`);
                const reasons = new Map();
                for (const item of result.skipped) {
                    reasons.set(item.reason, (reasons.get(item.reason) || 0) + 1);
                }
                for (const [reason, count] of reasons) console.log(`  - ${reason}（${count} 章）`);
                if (!cookie) {
                    console.log("  付费章节需登录：把浏览器 Cookie 传入 -c 参数，或写入 .cookie 文件。");
                }
            }
        } catch (error) {
            console.error(`导出失败：${error.message}`);
            process.exitCode = 1;
        }
    });

await program.parseAsync();
