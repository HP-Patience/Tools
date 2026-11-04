import { build } from "vite";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import {
  listFiles,
  readValidMap,
  releaseDir,
  root,
  sha,
  textSha,
  sourceFingerprint,
} from "./files";
import { verifyFiles, type ReleaseManifest } from "./release-core";
try {
  // Vite may empty this directory; verify the exact resolved output before building.
  if (
    releaseDir !== path.join(root, "release") ||
    path.relative(root, releaseDir) !== "release"
  )
    throw new Error("构建目录不安全");
  const { raw } = await readValidMap(path.join(root, "data/map.json"));
  const sourceHash = await sourceFingerprint();
  const builtAt = new Date().toISOString();
  const version =
    builtAt.replace(/[-:T]/g, "").slice(0, 14) + "-" + sourceHash.slice(0, 10);
  const info = { version, builtAt, sourceHash, mapHash: textSha(raw) };
  await build({
    base: `/versions/${version}/`,
    define: { __ATLAS_RELEASE__: JSON.stringify(info) },
  });
  await writeFile(
    path.join(releaseDir, "build-info.json"),
    JSON.stringify(info, null, 2) + "\n",
  );
  const files: Record<string, string> = {};
  for (const file of await listFiles(releaseDir))
    files[file] = sha(await readFile(path.join(releaseDir, file)));
  const manifest: ReleaseManifest = { schemaVersion: 1, ...info, files };
  await writeFile(
    path.join(releaseDir, "manifest.json"),
    JSON.stringify(manifest, null, 2) + "\n",
  );
  await verifyFiles(releaseDir, manifest);
  console.log(`发布产物已生成：${version}。请将 release/ 与对应源码一起提交。`);
} catch (error) {
  console.error(String(error));
  process.exitCode = 1;
}
