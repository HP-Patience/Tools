import { readFile } from "node:fs/promises";
import path from "node:path";
import { listFiles, sha } from "./files";
export interface ReleaseManifest {
  schemaVersion: 1;
  version: string;
  builtAt: string;
  sourceHash: string;
  mapHash: string;
  files: Record<string, string>;
}
export async function verifyFiles(
  directory: string,
  manifest: ReleaseManifest,
) {
  if (
    manifest.schemaVersion !== 1 ||
    !/^[0-9]{14}-[a-f0-9]{10}$/.test(manifest.version)
  )
    throw new Error("发布清单版本无效");
  if (
    !/^[a-f0-9]{64}$/.test(manifest.sourceHash) ||
    !/^[a-f0-9]{64}$/.test(manifest.mapHash)
  )
    throw new Error("发布指纹格式无效");
  if (
    !manifest.files ||
    typeof manifest.files !== "object" ||
    Array.isArray(manifest.files)
  )
    throw new Error("发布清单缺少文件列表");
  const actual = (await listFiles(directory)).filter(
    (f) => f !== "manifest.json",
  );
  if (
    JSON.stringify(actual) !==
    JSON.stringify(Object.keys(manifest.files).sort())
  )
    throw new Error("产物文件列表与清单不一致");
  if (!actual.includes("index.html") || !actual.includes("build-info.json"))
    throw new Error("缺少网站入口或版本信息");
  for (const file of actual) {
    if (
      !/^(index\.html|build-info\.json|assets\/[A-Za-z0-9_.-]+\.(js|css|json|svg|png|woff2|woff|ttf))$/.test(
        file,
      )
    )
      throw new Error(`不允许发布文件: ${file}`);
    if (
      sha(await readFile(path.join(directory, file))) !== manifest.files[file]
    )
      throw new Error(`产物哈希不一致: ${file}`);
  }
  const info = JSON.parse(
    await readFile(path.join(directory, "build-info.json"), "utf8"),
  );
  for (const key of ["version", "builtAt", "sourceHash", "mapHash"] as const)
    if (info[key] !== manifest[key])
      throw new Error(`版本元数据不一致: ${key}`);
  const html = await readFile(path.join(directory, "index.html"), "utf8");
  if (!html.includes(`/versions/${manifest.version}/assets/`))
    throw new Error("HTML 资源路径与发布版本不一致");
}

