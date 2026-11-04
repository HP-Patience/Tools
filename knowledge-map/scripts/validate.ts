import { readValidMap } from "./files";
try {
  const { data } = await readValidMap();
  console.log(
    `知识校验通过：${data.nodes.length} 个节点，${data.relations.length} 条关联。`,
  );
} catch (error) {
  console.error(
    `知识校验失败：\n${error instanceof Error ? error.message : error}`,
  );
  process.exitCode = 1;
}
