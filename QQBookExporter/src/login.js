/*
 * 扫码登录并自动抓取 Cookie
 * 打开真实浏览器 → 用户扫码登录 → 脚本轮询登录态 → 导出 Cookie 到 .cookie
 */
import fs from "node:fs";
import path from "node:path";
import { launchBrowser, DEFAULT_EDGE } from "./browser.js";

const HOME = "https://book.novel.qq.com/";
const COOKIE_DOMAINS = ["qq.com", "yuewen.com"];

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** 域名越具体越优先，避免同名 Cookie 取到父域旧值 */
function domainScore(domain) {
    return String(domain || "").split(".").filter(Boolean).length;
}

function collectCookies(cookies) {
    const usable = cookies
        .filter((c) => COOKIE_DOMAINS.some((d) => String(c.domain || "").replace(/^\./, "").endsWith(d)))
        .filter((c) => c.name && c.value !== undefined && c.value !== null)
        .sort((a, b) => domainScore(b.domain) - domainScore(a.domain));

    const map = new Map();
    for (const cookie of usable) {
        if (!map.has(cookie.name)) map.set(cookie.name, cookie.value);
    }
    return map;
}

/**
 * @param {{executablePath?: string, cookieFile?: string, timeoutMs?: number, keepOpen?: boolean}} options
 * @returns {Promise<{cookie: string, cookieFile: string, count: number}>}
 */
export async function captureCookie({
    executablePath = DEFAULT_EDGE,
    cookieFile = ".cookie",
    timeoutMs = 300000,
    keepOpen = false,
} = {}) {
    console.log("正在启动浏览器…");
    const { browser, close } = await launchBrowser({ executablePath, headless: false });

    try {
        const pages = await browser.pages();
        const page = pages[0] || (await browser.newPage());
        await page.goto(HOME, { waitUntil: "domcontentloaded", timeout: 60000 });

        // 尝试自动点开登录弹窗，省得用户找按钮
        await delay(1500);
        try {
            const clicked = await page.evaluate(() => {
                const nodes = [...document.querySelectorAll("a,button,div,span")].filter((el) => {
                    const text = (el.textContent || "").trim();
                    return /^(登录|立即登录|登录\/注册)$/.test(text) && el.offsetParent !== null;
                });
                if (!nodes.length) return false;
                nodes[nodes.length - 1].click();
                return true;
            });
            if (clicked) console.log("已自动打开登录弹窗。");
        } catch {
            // 自动点击失败不影响手动登录
        }

        console.log("");
        console.log("请在弹出的浏览器中点击右上角「登录」，用 QQ阅读 App 扫码。");
        const waitHint = timeoutMs >= 60000 ? `${Math.round(timeoutMs / 60000)} 分钟` : `${Math.round(timeoutMs / 1000)} 秒`;
        console.log(`登录成功后会自动保存 Cookie 到 ${path.resolve(cookieFile)}（最长等待 ${waitHint}）。`);
        console.log("");

        const deadline = Date.now() + timeoutMs;
        let loggedIn = false;
        let lastTip = Date.now();

        while (Date.now() < deadline) {
            if (!browser.connected) throw new Error("浏览器已关闭，登录未完成");

            try {
                loggedIn = await page.evaluate(async () => {
                    const response = await fetch("/api/user/baseInfo", { credentials: "include" });
                    const data = await response.json();
                    return Boolean(data?.isLogin ?? data?.data?.isLogin);
                });
            } catch {
                // 页面可能正在跳转或刷新，忽略后继续轮询
            }

            if (loggedIn) break;

            if (Date.now() - lastTip > 15000) {
                lastTip = Date.now();
                console.log("等待扫码中…");
            }
            await delay(1500);
        }

        if (!loggedIn) throw new Error("等待登录超时，请重试");

        await delay(1000);
        const client = await page.createCDPSession();
        const { cookies } = await client.send("Network.getAllCookies");
        const map = collectCookies(cookies);
        if (map.size === 0) throw new Error("登录成功但未取到 Cookie");

        const cookie = [...map].map(([name, value]) => `${name}=${value}`).join("; ");
        fs.writeFileSync(path.resolve(cookieFile), cookie, "utf-8");

        console.log(`登录成功，已保存 ${map.size} 个 Cookie → ${path.resolve(cookieFile)}`);
        if (!keepOpen) await close();
        return { cookie, cookieFile: path.resolve(cookieFile), count: map.size };
    } catch (error) {
        await close();
        throw error;
    }
}
