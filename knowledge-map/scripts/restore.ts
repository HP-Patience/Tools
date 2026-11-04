import { readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { atomicWrite, backupDir, mapFile, saveBackup } from "./files";
import { parseMap } from "../src/core/validate";
try {
  const dir = backupDir;
  const name = process.argv[2];
  if (!name || name === "--list") {
    console.log("可恢复版本（用 npm run restore -- 文件名 恢复）：");
    console.log(
      (await readdir(dir))
        .filter((n) => n.endsWith(".json"))
        .sort()
        .reverse()
        .join("\n"),
    );
  } else {
    if (
      !/^[0-9TZ-]+-[a-f0-9]{12}\.json$/.test(name) ||
      path.basename(name) !== name
    )
      throw new Error("仅允许备份目录中的有效文件名");
    const raw = await readFile(path.join(dir, name), "utf8");
    const result = parseMap(raw);
    if (!result.ok) throw new Error(result.errors.join("\n"));
    const current = await readFile(mapFile, "utf8");
    if (parseMap(current).ok) await saveBackup(current);
    else
      await writeFile(
        path.join(path.dirname(backupDir), `before-restore-${Date.now()}.txt`),
        current,
        "utf8",
      );
    await atomicWrite(mapFile, raw);
    console.log("已恢复：", name);
  }
} catch (error) {
  console.error(String(error));
  process.exitCode = 1;
}
