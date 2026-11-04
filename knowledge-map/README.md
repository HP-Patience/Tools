# 知序 · 我的知识，慢慢长成体系

个人 AI 辅助知识地图。**电脑上的 Agent 整理，多设备浏览器只读回看。**

没有内置模型、在线编辑或数据库。知识从空白生长，不用教材目录替你决定框架。

## 本地开始

需要 Node.js **24**、npm 和 Git。

```sh
npm ci
npm run dev
```

浏览器打开终端显示的本机地址（默认 `http://127.0.0.1:5173`）。页面初始为空，点“查看示例地图”可看独立示例。示例不会写进你的真实知识。

用任意本地 Agent 打开项目文件夹，开始对话：

> 先阅读 AGENTS.md。今天我学了过拟合，我理解是训练数据表现很好，换一批数据就不好了。复杂度和它有什么关系还不明白。帮我整理进地图，没有明确归属的先待归类。

Agent 修改 `data/map.json` 后，开发预览自动校验并更新。无效更新保留当前页面的上一份有效地图；关闭页面后再打开时若数据仍无效，应先用备份修复。

## 已实现

- 空地图、多顶层分支、父子布局、折叠展开、缩放平移、全图复位。
- 搜索标题/理解/疑问，搜索结果自动展开隐藏祖先并定位，Ctrl/Cmd+K。
- 节点理解、原表达、疑问、多个来源、AI 建议标识。
- 按选中节点显示跨知识关联，待归类区域。
- 桌面三栏、手机导航抽屉和可展开详情底部面板。
- JSON Schema + 语义校验、有效版本备份/恢复、本次变更提示。
- 本地版本化静态产物、完整性校验、GitHub Actions 发布、原子切换与回滚。
- Caddy 全站 Basic Auth 和 HTTPS 配置；不提供前端假登录。

## 常用命令

| 命令 | 用途 |
|---|---|
| `npm run dev` | 仅监听本机的开发预览 |
| `npm run schema:generate` | 修改 Schema 后更新无动态求值的预编译校验器 |
| `npm run validate` | 校验真实知识数据 |
| `npm run backup` | 保存有效备份，去重，最多保留 20 份 |
| `npm run restore -- --list` | 列出本机备份 |
| `npm run restore -- 文件名.json` | 校验并恢复某份备份，同时保留恢复前内容 |
| `npm run check` | 类型、真实数据、单元测试 |
| `npx playwright install chromium` | 安装浏览器测试运行时 |
| `npm run test:e2e` | 隔离数据的桌面/手机浏览器测试 |
| `npm run build` | 生成要提交的 `release/` |
| `npm run verify:release` | 拒绝源码不匹配或被篡改的产物 |
| `npm run preview` | 本机静态预览；使用终端给出的版本路径 |
| `python3 -m unittest discover -s tests/deploy -v` | Linux 部署集成测试（Windows 建议 WSL） |

发布产物使用版本化绝对资源地址。正式服务器从 `/` 提供页面，从 `/versions/<版本>/` 提供对应资源，旧页面不会因新发布而丢失资源。

## 文件结构

```text
data/map.json                   真实知识唯一数据源
examples/machine-learning.json  独立演示
AGENTS.md                       给本地 Agent 的工作规则
schema/map.schema.json          数据协议
src/                            React 只读展示
scripts/                        校验、备份、构建和发布验证
release/                        必须随对应源码提交的静态产物
.local/                         本机备份与测试文件，不提交
.github/workflows/              验证与发布流水线
deploy/                         Nginx/Caddy 配置、服务器切换/回滚脚本
docs/                           设计、数据格式、部署和验收说明
```

## 技术栈与部署边界

React + TypeScript + Vite、React Flow + Dagre、Ajv、Vitest + Playwright；当前服务器沿用 Nginx + Python 标准库部署脚本；仓库也提供 Caddy 部署模板。

私有 GitHub 仓库 → Actions 验证已提交的本地产物 → SSH 上传 → 服务器原子切换 → HTTPS + 密码查看。

当前站点：`https://121.41.92.58:18443`，Nginx + IP HTTPS 证书 + 全站 Basic Auth。私有仓库：`HP-Patience/knowledge-map`。首次手工安装已完成，GitHub 自动发布配置和实际运行状态见 `docs/ACCEPTANCE.md`。

不要把 Vite 开发端口暴露公网。完整步骤见 `docs/DEPLOYMENT.md`。

## 文档

- `MVP.md`：产品边界与验收目标。
- `docs/TECHNICAL_DESIGN.md`：技术栈和决策。
- `docs/DATA_FORMAT.md`：节点、来源、关系格式。
- `docs/DEPLOYMENT.md`：服务器初始配置、GitHub Secrets、发布和回滚。
- `docs/ACCEPTANCE.md`：实际测试结果与未完成的外部验收。

本版没有自动学习评分、整本教材解析、在线编辑或复杂账号系统。地图是否真正帮助理解，需要用你的真实学习主题连续使用后验证。

安全回归：Linux 运行 `bash deploy/install-test-caddy.sh`，然后 `python3 tests/security/caddy_smoke.py --caddy work/caddy --browser`。它使用临时凭据和回环 HTTP 验证真实 Caddy 认证规则及生产构建，结束后关闭临时服务。当前 Nginx 公网站点已验证可信 HTTPS 和未认证资源拦截；正确密码浏览器登录由用户自行验收。Caddy 冒烟不替代 Nginx 的真实部署验证。
