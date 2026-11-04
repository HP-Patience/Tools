/*
 * 浏览器启动器
 * Edge 155+ 在 Windows 上启动后会立即把进程交给新实例，导致 puppeteer 的
 * launch() 读不到 DevTools 地址而报 "Failed to launch the browser process!"。
 * 这里改为自行 spawn + 通过 DevTools 端口连接，绕开该问题。
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";

export const DEFAULT_EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function freePort() {
    return new Promise((resolve, reject) => {
        const server = net.createServer();
        server.unref();
        server.on("error", reject);
        server.listen(0, "127.0.0.1", () => {
            const { port } = server.address();
            server.close(() => resolve(port));
        });
    });
}

async function waitForDevTools(port, timeoutMs = 30000) {
    const deadline = Date.now() + timeoutMs;
    let lastError;
    while (Date.now() < deadline) {
        try {
            const response = await fetch(`http://127.0.0.1:${port}/json/version`);
            if (response.ok) return await response.json();
        } catch (error) {
            lastError = error;
        }
        await delay(300);
    }
    throw new Error(`浏览器 DevTools 未就绪：${lastError?.message || "等待超时"}`);
}

/**
 * @param {{executablePath?: string, headless?: boolean, persistProfile?: boolean}} options
 */
export async function launchBrowser({
    executablePath = DEFAULT_EDGE,
    headless = false,
    persistProfile = false,
} = {}) {
    if (!fs.existsSync(executablePath)) {
        throw new Error(`找不到浏览器：${executablePath}，可用 --edge 指定路径`);
    }

    const port = await freePort();
    const userDataDir = persistProfile
        ? path.join(process.cwd(), ".browser-profile")
        : path.join(os.tmpdir(), `qqbook-edge-${Date.now()}`);
    fs.mkdirSync(userDataDir, { recursive: true });

    const args = [
        `--remote-debugging-port=${port}`,
        `--user-data-dir=${userDataDir}`,
        "--no-first-run",
        "--no-default-browser-check",
        "--start-maximized",
    ];
    if (headless) args.push("--headless=new", "--disable-gpu");
    args.push("about:blank");

    const child = spawn(executablePath, args, { stdio: "ignore", windowsHide: false });
    let spawnError;
    child.on("error", (error) => {
        spawnError = error;
    });

    await waitForDevTools(port).catch((error) => {
        throw new Error(spawnError ? `启动浏览器失败：${spawnError.message}` : error.message);
    });

    const { default: puppeteer } = await import("puppeteer-core");
    const browser = await puppeteer.connect({
        browserURL: `http://127.0.0.1:${port}`,
        defaultViewport: null,
    });

    return {
        browser,
        port,
        async close() {
            try {
                await browser.close();
            } catch {
                // 浏览器可能已被用户关闭
            }
        },
    };
}
