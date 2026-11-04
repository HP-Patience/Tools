# GitHub CI/CD 与服务器原生部署修订

日期：2026-10-16。用户已确认部署方向；本文只更新设计和实施计划，不创建生产服务或开始产品开发。

## 已确认要求及技术假设

不使用 Docker Compose。代码上传 GitHub，由 CI/CD 更新服务器。默认以 GitHub Actions + SSH + Linux/systemd 为实施方案；服务器操作系统、架构、域名和访问参数需要在执行部署前确定。2026-10-17 已确定 React + Vite + TypeScript、FastAPI API 及 SQLite；前后端实施细节以同目录 `2026-10-17-react-fastapi-implementation.md` 为准。

## 发布流程

1. PR 及提交运行锁定依赖安装、业务测试、迁移一致性和构建检查；PR 工作流不能读取部署私钥。
2. 默认生产分支 main 推送且 CI 成功后发布，提供手动触发入口。发布同一环境串行执行，不取消正在进行的数据库迁移。
3. 以经过测试的确切 commit SHA 生成发布包，不在服务器随意拉取最新 main；排除本地数据库、测试数据、环境文件和 Git 凭据。React 前端构建为 dist 静态产物；Python 后端在独立 release 创建虚拟环境并安装锁定依赖。
4. SSH 上传至 `/srv/ai-subscriptions/releases/<sha>`；校验 SSH host key，使用专用部署身份和受限服务管理权限。
5. 共享目录 `/srv/ai-subscriptions/shared` 保存数据库、备份及生产环境文件；当前版本由 `current` 符号链接指向 release。仓库更新不得覆盖 shared。
6. 依赖和文件准备完成后，停止提醒 timer 及运行中的提醒任务，再停止应用服务；确认所有业务写入停止，再创建一致性备份并执行数据库迁移。
7. 迁移成功后切换 current，启动应用，访问本机健康检查与登录页，确认通过后恢复提醒 timer。健康检查只返回可用状态和发布 SHA，不返回配置或客户信息。
8. 失败时保留日志。无 schema 变更或 schema 向后兼容时可切回上一 release；不兼容迁移需在停写条件下人工确认恢复配套备份，不能声称只切换代码就完成数据库回滚。

GitHub Actions production 环境保存 SSH 主机、端口、用户、私钥和 known_hosts；不写进仓库或打印。邮件密码和应用密钥优先仅保存在服务器权限受控的环境文件。实际配置 GitHub Secrets、服务器服务及生产部署只在具备访问参数后执行。

应用进程采用 Uvicorn，由 systemd 管理；提醒服务运行 `python -m app.cli run-reminders`，数据库迁移使用 `alembic upgrade head`。前端构建为静态文件，Nginx 同域提供页面并转发 `/api/`。

## 提醒与备份

- systemd timer 每 15 分钟调用提醒命令，应用以 Asia/Hong_Kong 处理 09:00 发送及漏发恢复；服务需要系统时间同步。
- timer 使用 Persistent 以便开机后触发检查，应用仍必须自行扫描全部有效漏项，不依赖 timer 自动重放每次错过的运行。
- SQLite 建议使用本机持久磁盘、短写事务、唯一约束与 revision 条件更新；发送邮件在数据库写事务之外执行。不能使用 PostgreSQL 专用行锁或并发认领逻辑。
- SQLite 备份使用 sqlite3.Connection.backup() 或等效 Backup API，不能仅复制活跃 WAL 数据库主文件；备份在生产发布前及每天执行。
- 默认本机保留 14 份每日备份；本机备份不能抵抗整盘损坏。另提供加密异机备份步骤，其目的地和凭据明确前不得报告异机备份已启用。
- 并发发布、手动提醒和定时提醒共享数据库幂等机制；部署使用服务器发布锁，任务使用有界租约认领；发信结果不确定时记录状态而非假报成功。

## 文件与验收

实施时创建 `.github/workflows/ci.yml`、`deploy.yml`、`ops/deploy.sh`、`ops/systemd/ai-subscriptions.service`、`ai-subscriptions-reminders.service`、`ai-subscriptions-reminders.timer`、`ops/nginx.conf`、`ops/backup.py`、`ops/restore.py` 和 `docs/deployment.md`。当前只修改规划文档。

- [ ] 从干净 GitHub checkout 完成测试和构建，验证 PR 无生产凭据。
- [ ] 测试失败时不触发部署，多个推送不会同时迁移同一数据库。
- [ ] 使用服务器测试目录验证 release 切换；重复部署同一 SHA 无破坏性副作用。
- [ ] 新版本发布后客户、交易及提醒记录保持完整；生产库和环境文件不被覆盖。
- [ ] 验证迁移前备份、数据库完整性以及隔离恢复；验证一次代码回滚并说明 schema 限制。
- [ ] 模拟应用重启、提醒任务中断、跨提醒日期停机及恢复，检查有效漏项。
- [ ] 记录实际运行的版本、systemd 状态、timer 下一次运行时间和邮件测试结果。
- [ ] 服务器或 SMTP 访问参数未提供时，交付脚本及离线验证结果，明确实际发布尚未执行。

## 参考文档

```text
https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments
https://docs.sqlalchemy.org/en/20/dialects/sqlite.html
https://www.sqlite.org/backup.html
```
