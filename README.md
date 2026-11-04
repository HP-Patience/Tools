<p align="center">
  <img src="assets/readme/hero.svg" width="100%" alt="Tools：日常 AI 工具集合">
</p>

<p align="center">
  <strong>把散落在各处的日常小工具收进一个目录，每个工具保留自己的提交历史与远程仓库。</strong><br>
  子目录由 .gitignore 排除，工具各自独立 pull/push，本仓只负责索引与说明。
</p>

<p align="center">
  <a href="https://github.com/HP-Patience/Tools"><img src="https://img.shields.io/github/stars/HP-Patience/Tools?style=flat-square&color=f2c14e" alt="GitHub stars"></a>
  <a href="https://github.com/HP-Patience/Tools"><img src="https://img.shields.io/github/last-commit/HP-Patience/Tools?style=flat-square&color=3ec6b0" alt="最近提交"></a>
  <a href="https://github.com/HP-Patience/Tools"><img src="https://img.shields.io/github/languages/top/HP-Patience/Tools?style=flat-square&color=8b93a1" alt="主要语言"></a>
  <a href="#工具清单"><img src="https://img.shields.io/badge/tools-11-ff7a59?style=flat-square" alt="工具数量：11"></a>
</p>

## 这是什么

日常在用的小工具合集。它们语言、运行形态各不相同——Python 脚本、Go 服务、TypeScript 应用、纯静态页——没有可以共用的代码层，所以不合并历史，只归拢位置。

放在一起的理由只有一个：**要找的时候知道去哪儿找**。

## 目录

| 目录 | 说明 | 形态 |
|---|---|---|
| `GPT图像工坊` | 本地图像生成与提示词试验台 | 静态页 |
| `LLM试金石` | 多模型服务连通性与质量测试 | 静态页 |
| `Dreamcore-Style-Transfer` | 10 种亚文化美学的纯 Pillow 图像处理 | Python |
| `Penrose-Staircase` | 彭罗斯不可能阶梯生成器 | Python |
| `tencent-server-seckill` | 腾讯云服务器抢购助手 | Python |
| `mailbox-reader` | Windows 本地邮箱批量读取（Graph API） | Python |
| `QQBookExporter` | QQ 阅读书籍导出（Markdown / EPUB） | Node |
| `danew_card_cdk` | CDK 卡密兑换与自动开通 | Go + Vue |
| `ai-subscription-manager` | AI 订阅客户与续费管理 | TypeScript |
| `Taskleaf-Kanban` | 四列任务看板，JSON 持久化 | 原生 JS |
| `knowledge-map` | AI 整理、人只读的知识地图 | TypeScript |

## 为什么这样放

嵌套的 `.git` 会被外层仓库当作 gitlink，`git add .` 会生成一批没有 `.gitmodules` 的假子模块。所以本仓的 `.gitignore` 显式排除了这些目录：

```gitignore
/Dreamcore-Style-Transfer/
/tencent-server-seckill/
/...
```

结果是：外层 `git status` 干净，子仓仍可各自 `git pull` / `git push`。

## 怎么用

```bash
git clone https://github.com/HP-Patience/Tools.git
cd Tools/<工具名>
```

每个子目录都有独立的 `README.md` 与 `package.json` / `requirements.txt`，按各自说明安装即可。

## 说明

- 子仓的远程仓库部分已删除，代码只保留在本地这份工作区，`git fetch` 会报 `Repository not found`，属预期。
- 新增工具时，记得同步更新本 README 的目录表与 `.gitignore`。
