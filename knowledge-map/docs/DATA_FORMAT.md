# 知识数据协议 v1

`data/map.json` 是真实数据，UTF-8 JSON，可带 BOM。`schema/map.schema.json` 为机器协议，以 `npm run validate` 的结果为准。文本按纯文字显示，不执行 HTML，不支持富文本脚本。

## 空地图

```json
{
  "schemaVersion": 1,
  "id": "my-map",
  "title": "我的知识地图",
  "description": "由我的理解逐渐建立",
  "updatedAt": "2026-09-10T00:00:00Z",
  "nodes": [],
  "relations": [],
  "sources": []
}
```

## 节点

```json
{
  "id": "overfitting",
  "title": "过拟合",
  "parentId": null,
  "placement": "unassigned",
  "overview": "过拟合是模型在训练数据上表现很好，但在新的同类数据上表现较差的现象，关键在于它没能把训练时学到的规律有效用于新数据。",
  "summary": "什么是过拟合\n\n训练数据是模型学习时使用的数据。判断模型是否学到了可用于新数据的规律，不能只看它在训练数据上的表现，还需要看它面对未参与训练的同类数据时表现如何。\n\n如果模型在训练数据上表现很好，换成新的同类数据后表现却明显变差，就可能出现了过拟合。因此，训练表现好不等于在新数据上也能表现好。",
  "originalExpression": "我大概理解就是训练时很好，但换了数据就不行。",
  "provenance": "suggestion",
  "questions": [
    {"id": "complexity-question", "text": "为什么和模型复杂度有关？", "status": "open"}
  ],
  "sourceIds": [],
  "createdAt": "2026-09-10T00:00:00Z",
  "updatedAt": "2026-09-10T00:00:00Z"
}
```

- ID 使用稳定的 ASCII 标识，不用标题作引用键。改名不改 ID。
- `parentId` 是父节点 ID，根节点用 null。一个节点只有一个结构父节点，允许多个根；禁止父子循环。
- `placement: main` 表示主图；`unassigned` 必须无父节点，也不能作为其他节点的父节点。
- `overview` 可省略，最长 500 字符；新整理节点应提供非空的一段话概览。`summary` 为必填字符串，可为空，最长 12000 字符；`originalExpression` 可省略。旧节点缺少概览时，不用截断正文冒充概览。
- `provenance: user` 为用户表达；`material` 为材料整理；`suggestion` 为 AI 建议待确认。一个节点只标一种性质，不把 AI 建议直接混入用户理解。
- 疑问 status 是 `open` 或 `resolved`。resolved 表示记录已解决，不是自动掌握度。
- `sourceIds` 可空；非空项必须引用真实存在的来源。
- 时间用完整 ISO 8601，更新时间不能早于创建时间。

### 三个文本字段的职责

| 字段 | 内容 | 阅读方式（界面目标） |
| --- | --- | --- |
| `overview` | 用一段话概括整个节点的核心问题、结论与必要条件；不是目录、正文截断或聊天总结 | 顶部“一段话描述”，常显 |
| `summary` | 教材式正文，让读者不必回看对话也能理解；按需要组织定义、条件、解释、例子、公式与推导 | “正文”，可独立展开/收起 |
| `originalExpression` | 确实需要保留的用户原话，逐字记录；不是第二份教材，不用 AI 纠正版替换 | 独立“原始表达”，默认收起；无内容不显示 |

`summary` 保留字段名以兼容现有数据，但含义是完整学习正文，而不是短摘要。正文以清晰阅读为目标：用自然小标题、段落和换行，不要求固定栏目，不加入“AI 补充/用户理解/理解反馈”等逐段来源标签。过去的疑惑可转为自然解释；有价值的推导不能在改写时被摘要替代。当前纯文本渲染，不依赖 Markdown 或 LaTeX 排版。

上例是 AI 教材式草稿，因此使用 `suggestion`；即便保留了用户原话，也不意味着整篇都是用户独立表达。示例仅说明格式，不能自动导入真实图谱。

来源归 `provenance` / `sourceIds`，疑问归 `questions`。当前仅支持节点级性质，不新增段落级标注协议。单纯润色保持原性质；未经审核的 AI 实质性新增先给草稿，或获准后另存为 suggestion，不能静默混入 user/material 正文。批准记录不自动改变性质，也不代表掌握。

已有正文的教材式替换先给完整草稿，经用户审核后再备份写入；保留稳定 ID、原始表达、来源、关系和疑问状态，不批量重写其他节点。

## 来源

```json
{"id":"course-video","title":"某课程的一节视频","kind":"course","locator":"第 3 讲，12:30"}
```

`kind` 可为 book/course/article/practice/conversation/other；`url` 和 `locator` 可省略。
URL 只接受无用户名密码的 HTTP(S) 链接，禁止 javascript、data、file 等协议。这里仅记录链接，不自动下载或解析材料。标题请填写可识别的来源名称，不必补填没有的信息。

## 跨节点关系

```json
{"id":"complexity-overfit","source":"complexity","target":"overfitting","label":"可能影响","description":"具体机制尚未弄懂。","status":"suggested"}
```

端点必须存在，不允许自关联或完全重复的关系。`confirmed` 表示用户确认记录的联系，`suggested` 为待确认建议。关系有方向，但不参与主干排版；详情中可从任一端导航到另一端。

## 修改与恢复

1. 先备份，再做局部修改；不要重建整个 JSON 后丢弃无关字段。
2. 删除节点前检查它的孩子和关系；移除来源前清理 `sourceIds`。大结构修改由用户确认。
3. 保存后必须校验。开发页面的“保留旧图”仅保护当前浏览会话，不自动覆盖错误文件。
4. `npm run restore -- --list` 查看有效备份，再按文件名恢复。Git 记录是额外版本历史，不取代本机备份。
5. 测试使用 `.local/e2e-map.json` 与 `.local/e2e-backups`，不改真实知识及真实备份。

单文件方案服务个人 MVP。当前 Schema 允许的上限不等于性能承诺；先以数十到数百节点使用验证，超大知识库的虚拟化、分片和增量布局不在本版范围。
