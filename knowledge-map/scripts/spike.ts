import sample from "../examples/machine-learning.json";
import { validateMap } from "../src/core/validate";
import { layoutNodes } from "../src/core/graph";
const result = validateMap(sample);
if (!result.ok) throw new Error(result.errors.join("\n"));
console.log(
  "Dagre 技术验证:",
  layoutNodes(result.data.nodes).size,
  "个节点已布局",
);
