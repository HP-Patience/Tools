<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="Tools：12 个日常工具放在一个仓库，克隆一次即可全部取到">
</p>

<p align="center">
  <strong>把日常在用的 12 个小工具收进一个仓库，每个工具保留自己的 README 与运行方式。</strong><br>
  形态从静态页到 Go 后端各不相同，没有共用代码层，因此共享位置而不共享依赖。
</p>

<p align="center">
  <a href="https://github.com/wilsoncslearn/AI_Tools"><img src="https://img.shields.io/github/stars/wilsoncslearn/AI_Tools?style=flat-square&labelColor=0b0f14&color=5fd0bb" alt="GitHub stars"></a>
  <a href="https://github.com/wilsoncslearn/AI_Tools/commits/main"><img src="https://img.shields.io/github/last-commit/wilsoncslearn/AI_Tools?style=flat-square&labelColor=0b0f14&color=5fd0bb" alt="最近一次提交"></a>
  <a href="https://github.com/wilsoncslearn/AI_Tools"><img src="https://img.shields.io/github/languages/top/wilsoncslearn/AI_Tools?style=flat-square&labelColor=0b0f14&color=e4af77" alt="主要语言"></a>
  <a href="#工具清单"><img src="https://img.shields.io/badge/tools-12-e4af77?style=flat-square&labelColor=0b0f14" alt="工具数量 12"></a>
</p>

## 这是什么

日常在用的小工具合集。12 个工具的形态各不相同——静态页、Python 脚本、Node 服务、Go 后端、TypeScript 应用，外加一个浏览器游戏原型——没有可以共用的代码层，所以不合并依赖，只归拢位置。

放在一起的理由只有一个：**要找的时候知道去哪儿找**。

## 工具清单

| 工具 | 做什么 |
|---|---|
| [`GPT图像工坊`](./GPT图像工坊/) | 输入提示词生成图片，支持参考图编辑与本地标注 · FastAPI |
| [`LLM试金石`](./LLM试金石/) | 批量验证 OpenAI 兼容接口的模型连通性与耗时 · 静态页 |
| [`Dreamcore-Style-Transfer`](./Dreamcore-Style-Transfer/) | 用 Pillow 做 10 种「核」风格的像素级处理 · Python |
| [`Penrose-Staircase`](./Penrose-Staircase/) | 生成第 n 阶彭罗斯不可能阶梯 · Python |
| [`tencent-server-seckill`](./tencent-server-seckill/) | 腾讯云服务器抢购的本地控制台与命令行 · Python + Playwright |
| [`mailbox-reader`](./mailbox-reader/) | 批量导入邮箱，按需读取收件箱 · Python + Graph API |
| [`QQBookExporter`](./QQBookExporter/) | 导出在线章节为 Markdown / TXT，再打包 EPUB / PDF · Node.js |
| [`Taskleaf-Kanban`](./Taskleaf-Kanban/) | 四列任务看板，JSON 文件持久化 · 原生 JS + Vite + Express |
| [`ai-subscription-manager`](./ai-subscription-manager/) | AI 订阅客户、续费与利润记录，到期邮件提醒 · React + FastAPI + SQLite |
| [`danew_card_cdk`](./danew_card_cdk/) | CDK 卡密兑换与自动开通 · Go + Vue |
| [`knowledge-map`](./knowledge-map/) | Agent 整理、浏览器只读回看的个人知识地图 · TypeScript + Vite |
| [`ember-covenant-sanctuary`](./ember-covenant-sanctuary/) | 像素风俯视角动作肉鸽原型《烬契圣堂》，七重圣堂 + 双面契印构筑 · Phaser 3 + VibeGame |

## 目录结构

```text
Tools/
├── GPT图像工坊/
├── LLM试金石/
├── Dreamcore-Style-Transfer/
├── Penrose-Staircase/
├── tencent-server-seckill/
├── mailbox-reader/
├── QQBookExporter/
├── Taskleaf-Kanban/
├── ai-subscription-manager/
├── danew_card_cdk/
├── knowledge-map/
├── ember-covenant-sanctuary/
├── assets/readme/
└── README.md
```

一个工具一个目录，目录内自带 `README.md` 与依赖清单（`requirements.txt` / `package.json` / `go.mod`）。

## 怎么用

```bash
git clone https://github.com/wilsoncslearn/AI_Tools.git
cd AI_Tools
```

进入对应目录，按该目录的 `README.md` 运行。两个 Python 工具可以直接这样起步：

```bash
cd LLM试金石
python server.py
```

```bash
cd GPT图像工坊
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## 新增一个工具

1. 在根目录建一个独立目录，内含自己的 `README.md` 与依赖清单。
2. 在目录内放 `.gitignore`，排除依赖目录、构建产物、`.env` 与本地数据。
3. 在本 README 的工具清单与目录结构里补上这一项。
4. 不提交 `.env`、API Key、Token、Cookie 与本地数据库。

## 说明

- 12 个项目共用一个仓库，但依赖与运行环境彼此独立，建议每个 Python 工具各自建虚拟环境。
- 各工具的 `.env`、`data/`、`output/` 等由目录内的 `.gitignore` 排除，不随仓库分发。
- 运行环境要求以各工具自己的 `README.md` 为准，例如 `knowledge-map` 与 `Taskleaf-Kanban` 需要 Node.js 24。
- 本仓在 `wilsoncslearn/AI_Tools` 与 `HP-Patience/Tools` 各有一份，内容一致，克隆任一地址均可。
