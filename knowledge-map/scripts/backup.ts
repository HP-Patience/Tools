import { readValidMap, saveBackup } from "./files";
try {
  const { raw } = await readValidMap();
  console.log("有效版本已备份：", await saveBackup(raw));
} catch (error) {
  console.error(String(error));
  process.exitCode = 1;
}
