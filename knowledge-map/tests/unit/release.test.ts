import { afterEach, describe, expect, it } from "vitest";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { sha, textSha } from "../../scripts/files";
import { verifyFiles, type ReleaseManifest } from "../../scripts/release-core";
const temps: string[] = [];
afterEach(async () => {
  for (const dir of temps.splice(0))
    await rm(dir, { recursive: true, force: true });
});
async function fixture() {
  const dir = await mkdtemp(path.join(os.tmpdir(), "zhixu-release-"));
  temps.push(dir);
  const info = {
    version: "20260910000000-aaaaaaaaaa",
    builtAt: "2026-09-10T00:00:00.000Z",
    sourceHash: "a".repeat(64),
    mapHash: "b".repeat(64),
  };
  const files = {
    "index.html": `<script src="/versions/${info.version}/assets/app.js"></script>`,
    "build-info.json": JSON.stringify(info),
    "assets/app.js": 'console.log("test")',
  };
  await mkdir(path.join(dir, "assets"));
  for (const [file, content] of Object.entries(files))
    await writeFile(path.join(dir, file), content);
  const manifest: ReleaseManifest = {
    schemaVersion: 1,
    ...info,
    files: Object.fromEntries(
      Object.entries(files).map(([file, content]) => [file, sha(content)]),
    ),
  };
  await writeFile(path.join(dir, "manifest.json"), JSON.stringify(manifest));
  return { dir, manifest };
}
describe("发布完整性", () => {
  it("完整产物通过", async () => {
    const { dir, manifest } = await fixture();
    await expect(verifyFiles(dir, manifest)).resolves.toBeUndefined();
  });
  it("篡改产物拒绝", async () => {
    const { dir, manifest } = await fixture();
    await writeFile(path.join(dir, "assets/app.js"), "tampered");
    await expect(verifyFiles(dir, manifest)).rejects.toThrow("哈希");
  });
  it("多出秘密文件拒绝", async () => {
    const { dir, manifest } = await fixture();
    await writeFile(path.join(dir, ".env"), "secret");
    await expect(verifyFiles(dir, manifest)).rejects.toThrow("列表");
  });
  it("缺失资源拒绝", async () => {
    const { dir, manifest } = await fixture();
    await rm(path.join(dir, "assets/app.js"));
    await expect(verifyFiles(dir, manifest)).rejects.toThrow("列表");
  });
  it("无效版本拒绝", async () => {
    const { dir, manifest } = await fixture();
    manifest.version = "../outside";
    await expect(verifyFiles(dir, manifest)).rejects.toThrow("版本");
  });
  it("元数据替换拒绝", async () => {
    const { dir, manifest } = await fixture();
    const file = path.join(dir, "build-info.json");
    const info = JSON.parse(await readFile(file, "utf8"));
    info.version = "other";
    const raw = JSON.stringify(info);
    await writeFile(file, raw);
    manifest.files["build-info.json"] = sha(raw);
    await expect(verifyFiles(dir, manifest)).rejects.toThrow("元数据");
  });
  it("源文本指纹不受 Windows 换行影响", () =>
    expect(textSha("a\r\nb\r\n")).toBe(textSha("a\nb\n")));
});
