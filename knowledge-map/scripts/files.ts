import { createHash } from "node:crypto";
import {
  readFile,
  readdir,
  mkdir,
  writeFile,
  rename,
  unlink,
} from "node:fs/promises";
import path from "node:path";
import { parseMap } from "../src/core/validate.ts";
export const root = process.cwd();
export const mapFile = path.resolve(
  root,
  process.env.ATLAS_MAP_FILE || "data/map.json",
);
export const backupDir = path.resolve(
  root,
  process.env.ATLAS_BACKUP_DIR || ".local/backups",
);
export const releaseDir = path.resolve(root, "release");
export const sha = (value: string | Buffer) =>
  createHash("sha256").update(value).digest("hex");
export const textSha = (value: string) => sha(value.replace(/\r\n/g, "\n"));
export async function readValidMap(file = mapFile) {
  const raw = await readFile(file, "utf8");
  const result = parseMap(raw);
  if (!result.ok) throw new Error(result.errors.join("\n"));
  return { raw, data: result.data };
}
export async function listFiles(
  directory: string,
  prefix = "",
): Promise<string[]> {
  const result: string[] = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.isSymbolicLink())
      throw new Error(`不允许符号链接: ${entry.name}`);
    const relative = prefix + entry.name;
    if (entry.isDirectory())
      result.push(
        ...(await listFiles(path.join(directory, entry.name), relative + "/")),
      );
    else if (entry.isFile()) result.push(relative);
  }
  return result.sort();
}
export async function sourceFingerprint() {
  const entries = [
    "package.json",
    "package-lock.json",
    "index.html",
    "tsconfig.json",
    "vite.config.ts",
  ];
  for (const dir of ["src", "scripts", "schema", "data", "examples"])
    for (const file of await listFiles(path.join(root, dir)))
      entries.push(`${dir}/${file}`);
  const hashes: Record<string, string> = {};
  for (const entry of entries.sort())
    hashes[entry] = textSha(await readFile(path.join(root, entry), "utf8"));
  return sha(JSON.stringify(hashes));
}
export async function saveBackup(raw: string) {
  const valid = parseMap(raw);
  if (!valid.ok) throw new Error("仅备份通过校验的知识文件");
  const dir = backupDir;
  await mkdir(dir, { recursive: true });
  const digest = sha(raw).slice(0, 12);
  const previous = (await readdir(dir))
    .filter((n) => n.endsWith(".json"))
    .sort();
  if (previous.some((n) => n.endsWith(`-${digest}.json`)))
    return previous.find((n) => n.endsWith(`-${digest}.json`))!;
  const file = `${new Date().toISOString().replace(/[:.]/g, "-")}-${digest}.json`;
  await writeFile(path.join(dir, file), raw, "utf8");
  const all = [...previous, file].sort();
  for (const old of all.slice(0, Math.max(0, all.length - 20)))
    if (/^[0-9TZ-]+-[a-f0-9]{12}\.json$/.test(old))
      await unlink(path.join(dir, old));
  return file;
}
export async function atomicWrite(file: string, raw: string) {
  const temp = file + `.tmp-${process.pid}`;
  await writeFile(temp, raw, "utf8");
  await rename(temp, file);
}
