import { afterEach, describe, expect, it } from "vitest";
import { mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import os from "node:os";
import path from "node:path";
import demo from "../../examples/machine-learning.json";
const exec = promisify(execFile);
const temps: string[] = [];
afterEach(async () => {
  for (const dir of temps.splice(0))
    await rm(dir, { recursive: true, force: true });
});
async function fixture() {
  const dir = await mkdtemp(path.join(os.tmpdir(), "zhixu-backup-"));
  temps.push(dir);
  const file = path.join(dir, "map.json");
  const backups = path.join(dir, "backups");
  const raw = JSON.stringify(demo);
  await writeFile(file, raw);
  const run = (script: string, args: string[] = []) =>
    exec(
      process.execPath,
      ["--import", "tsx", `scripts/${script}.ts`, ...args],
      {
        env: {
          ...process.env,
          ATLAS_MAP_FILE: file,
          ATLAS_BACKUP_DIR: backups,
        },
      },
    );
  return { dir, file, backups, raw, run };
}
describe("有效备份与恢复 CLI", () => {
  it("相同有效内容只备份一次", async () => {
    const f = await fixture();
    await f.run("backup");
    await f.run("backup");
    expect(await readdir(f.backups)).toHaveLength(1);
  });
  it("拒绝备份无效文件", async () => {
    const f = await fixture();
    await writeFile(f.file, "{");
    await expect(f.run("backup")).rejects.toThrow();
  });
  it("恢复有效版本并保存损坏原文", async () => {
    const f = await fixture();
    await f.run("backup");
    const [name] = await readdir(f.backups);
    await writeFile(f.file, "broken");
    await f.run("restore", [name]);
    expect(await readFile(f.file, "utf8")).toBe(f.raw);
    const recovery = (await readdir(f.dir)).find((n) =>
      n.startsWith("before-restore"),
    )!;
    expect(await readFile(path.join(f.dir, recovery), "utf8")).toBe("broken");
  });
  it("恢复拒绝目录穿越", async () => {
    const f = await fixture();
    await expect(f.run("restore", ["../map.json"])).rejects.toThrow();
    expect(await readFile(f.file, "utf8")).toBe(f.raw);
  });
});
