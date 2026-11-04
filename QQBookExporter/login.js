#!/usr/bin/env node
/*
 * 单独运行：扫码登录并把 Cookie 保存到 .cookie
 * 之后 exporter.js 会自动读取该文件。
 */
import { Command } from "commander";
import { captureCookie } from "./src/login.js";

const program = new Command();
program
    .name("qqbook-login")
    .description("扫码登录轻小说网 / QQ阅读，自动保存 Cookie 到 .cookie")
    .option("-f, --file <path>", "Cookie 保存路径", ".cookie")
    .option("-t, --timeout <seconds>", "等待扫码的超时时间（秒）", "300")
    .option("--edge <path>", "浏览器路径")
    .option("--keep-open", "保存后不关闭浏览器")
    .action(async (options) => {
        try {
            const { cookie, cookieFile, count } = await captureCookie({
                executablePath: options.edge,
                cookieFile: options.file,
                timeoutMs: Number(options.timeout) * 1000,
                keepOpen: options.keepOpen,
            });
            console.log("");
            console.log(`已保存 ${count} 个 Cookie：${cookieFile}`);
            console.log(`Cookie 长度 ${cookie.length} 字符，可直接运行：node exporter.js <bookId>`);
        } catch (error) {
            console.error(`登录失败：${error.message}`);
            process.exitCode = 1;
        }
    });

await program.parseAsync();
