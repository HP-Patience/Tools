import { readFile } from "node:fs/promises";
import path from "node:path";
import {
  readValidMap,
  releaseDir,
  root,
  textSha,
  sourceFingerprint,
} from "./files";
import { verifyFiles, type ReleaseManifest } from "./release-core";
try {
  const manifest = JSON.parse(
    await readFile(path.join(releaseDir, "manifest.json"), "utf8"),
  ) as ReleaseManifest;
  const { raw } = await readValidMap(path.join(root, "data/map.json"));
  if (manifest.mapHash !== textSha(raw))
    throw new Error("知识数据已修改，请重新本地构建");
  if (manifest.sourceHash !== (await sourceFingerprint()))
    throw new Error("源文件与本地构建产物不一致，请重新执行 npm run build");
  await verifyFiles(releaseDir, manifest);
  console.log("发布校验通过：", manifest.version);
} catch (error) {
  console.error(`拒绝发布：${String(error)}`);
  process.exitCode = 1;
}
