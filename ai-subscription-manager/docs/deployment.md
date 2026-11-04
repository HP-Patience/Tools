# 部署方式

## 普通用户部署（当前服务器）

当前已按用户要求启用公网 HTTP：`http://110.42.237.129:18080`。服务器配置 `APP_BIND_HOST=0.0.0.0`、`APP_APP_URL=http://110.42.237.129:18080`；端口已由用户在云控制台开放。沿用现有管理员和数据库，不配置 HTTPS。

以下 SSH 隧道方式保留为初始部署说明；当前登录来源以公网地址为准。若恢复私有模式，将 APP_BIND_HOST 改为 127.0.0.1、APP_APP_URL 改为 http://localhost:18080，再重启服务。

当前以 `work` 用户运行，目录 `/home/work/apps/ai-subscriptions`。服务器没有免密 sudo，因此不修改系统服务、Nginx、其他应用或防火墙。

- FastAPI 同源提供构建后的 React 页面与 API；监听地址由 APP_BIND_HOST 控制，当前为 `0.0.0.0:18080`。
- user crontab 负责启动/恢复服务、每 15 分钟扫描到期提醒和每日备份；与系统级部署互为替代，不重复启用两套任务。
- `shared/app.env` 和 SQLite 数据库独立于 releases。当前按用户选择使用公网 HTTP，页面访问来源须与 APP_APP_URL 一致。
- 首次管理员由用户在网页设置，服务器不导入本地数据库、演示数据或临时管理员。

恢复 SSH 私有模式后，可保持以下命令运行，再用浏览器访问 `http://localhost:18080`：

```sh
ssh -N -L 18080:127.0.0.1:18080 work@110.42.237.129
```

普通用户部署脚本在 `ops/user/`。初始化工具使用官方发布并核对 SHA256 的 uv，不安装系统软件。发布包只含代码和前端构建产物，不能包含 `.env`、数据库或私钥。

GitHub Actions 的 `DEPLOY_ROOT` 设为 `/home/work/apps/ai-subscriptions`；独立部署密钥仅允许向 incoming 上传 SHA 命名的发布包及执行部署命令，不能打开交互 shell、读取其他目录或转发端口。个人 SSH 密钥不上传 GitHub。

服务日志在 `logs/service.log`，任务日志在 `logs/tasks.log`；本应用的 cron 行带 `ai-subscriptions-managed` 标识，保留其他 cron 项。SMTP 尚未配置时可先使用其他功能；配置后从提醒页测试发送。

公网 HTTP 是用户明确选择的当前模式；需要 HTTPS 时再配置域名、证书与入口。

## 系统级部署（有 sudo 和 HTTPS 时可选）


## 前提与目录

准备一台支持 Python 3.12、systemd 和 Nginx 的 Linux 主机及已配置 HTTPS 的域名。CI 构建前端，服务器只需 Python 运行时、venv、SSH、curl、tar 和 util-linux 的 flock。第一次服务器准备由拥有权限的运维者执行；下列脚本尚未在真实服务器运行。

```text
/srv/ai-subscriptions/
  deploy.sh                 运维安装的发布脚本
  incoming/                 CI 上传的发布包
  releases/<commit-sha>/     应用、前端静态文件及独立虚拟环境
  current -> releases/...   当前版本
  shared/app.env            生产配置（权限 600）
  shared/subscriptions.db   持久化业务数据库
  shared/backups/           数据库一致性备份
```

建议专用账号 `subscription` 拥有应用目录，SSH 发布使用该账号；Nginx 用户需要读取 frontend/dist 和目录遍历权限，但不能读取 shared。生产 SQLite、WAL 及环境文件应为仅应用账号可访问，备份目录权限 700。不要给发布账号无限 sudo 权限，只允许启动/停止本文列出的应用、提醒及备份 unit。

## 首次准备

1. 创建账号、上述目录，安装 Python 3.12、venv、Nginx 和证书；部署包不安装系统组件。
2. 将 `ops/deploy.sh` 安装为固定路径 `/srv/ai-subscriptions/deploy.sh`，由运维审阅后更新。该脚本和 CI 使用的脚本版本应一起维护，不从未经测试的分支直接运行。
3. 将 `ops/systemd/` 的五个 unit 安装到 `/etc/systemd/system/`，执行 daemon-reload。暂不启动 unit，直到第一次发布成功。
4. 设置 shared/app.env，示例如下。密码由运维填写，不复制到仓库：

```dotenv
APP_PRODUCTION=true
APP_APP_URL=https://你的实际域名
APP_DATABASE_PATH=/srv/ai-subscriptions/shared/subscriptions.db
APP_MAIL_BACKEND=smtp
APP_SMTP_HOST=你的邮件服务主机
APP_SMTP_PORT=587
APP_SMTP_FROM=已验证的发件地址
APP_SMTP_USERNAME=邮件账号
APP_SMTP_PASSWORD=邮件授权密码
APP_SMTP_STARTTLS=true
APP_SMTP_SSL=false
```

465 端口通常使用 SSL=true、STARTTLS=false，具体按邮件供应商要求填写。未准备好 SMTP 时设置 MAIL_BACKEND=disabled，其余业务照常运行。

5. 修改 `ops/nginx.conf` 的域名与证书路径，并在测试通过后安装启用；`/api/` 不允许回退至前端 index.html。
6. 在 GitHub 创建 production environment，配置 secrets：DEPLOY_HOST、DEPLOY_PORT（可选，默认22）、DEPLOY_USER、DEPLOY_SSH_KEY、DEPLOY_KNOWN_HOSTS。known_hosts 来自运维已核实的服务器公钥，不在流水线中盲目信任 ssh-keyscan。
7. 设置仓库 Actions variable `DEPLOY_ENABLED=true` 才启用生产发布。未设置时仍运行 CI 和构建产物，避免新仓库尚未配置服务器就失败部署。
8. 推送 main；CI 通过后以确切 SHA 的已测试产物发布。首次发布可先不打开部署开关，在服务器人工验证同一发布包。失败要查日志，不复制开发数据库作为生产初始化。

## 首次管理员与任务启用

第一次发布迁移会创建空业务库。在仅自己可访问的环境中打开网页，完成“设置管理员账户”后再开放正式域名访问；填写账号和两次密码后自动登录，初始化入口随即关闭。也可先通过 current/.venv/bin/python 的 `-m app.cli bootstrap-owner` 交互式创建唯一管理员。生产不运行 seed-demo。

确认登录、HTTPS、邮件设置页测试投递通过后启用：

```sh
sudo systemctl enable ai-subscriptions.service
sudo systemctl enable --now ai-subscriptions-reminders.timer
sudo systemctl enable --now ai-subscriptions-backup.timer
sudo systemctl list-timers 'ai-subscriptions-*'
```

应用命令由 systemd 管理，仅监听 127.0.0.1。提醒任务为独立 oneshot；即使关闭浏览器，系统定时器仍运行。系统时间需正确同步；业务时区固定香港，timer 可每15分钟按服务器时区触发，应用内部按香港时间判断09:00和补发。

## 发布、失败与回滚

流水线和服务器各自串行发布。先准备新 release 及安装依赖，再停提醒和备份 timer、停止运行中的任务和应用，做一致性备份，执行 Alembic 迁移，原子切换 current，启动并核对健康检查中的版本 SHA，最后恢复 timer。

若备份、迁移或健康检查失败，脚本退出并保留数据与日志；服务或 timer 可能停着，需要运维检查后恢复，不能把失败当成功。脚本不自动回退数据库。

重新发布同一 SHA 前检查 `current.next` 是否为脚本残留的符号链接；激活脚本只替换符号链接，不删除 release 目录。旧 release 不自动清理，确认回滚窗口后由运维处理。

代码回滚仅在 schema 向后兼容时切换 current 并重启服务。若迁移不兼容，应保持全部写入停止，在独立目标恢复备份并核验，再由运维明确选择生产恢复时间点；恢复旧备份会丢失该备份之后的业务写入，不能自动执行。

## 备份恢复

每天备份及发布前备份均通过 SQLite Backup API，使用 integrity_check，不只复制活跃 WAL 库的主文件。默认保留最近14个快照（包含发布前备份，因此多次发布会减少覆盖的自然天数）。

```sh
python ops/backup.py /srv/ai-subscriptions/shared/subscriptions.db /srv/ai-subscriptions/shared/backups
python ops/restore.py 指定备份文件 /srv/ai-subscriptions/shared/restore-verification.db
```

恢复工具拒绝覆盖任何已存在的目标。实际恢复演练需比较 customers、sales、services、reminders 的计数及关键交易值。单机备份无法抵抗整盘损坏；配置加密异机备份目标和凭据后，另行验证上传与恢复，当前没有宣称已启用。

## 验收边界

本地自动测试可验证交易、提醒逻辑、浏览器操作及备份恢复；GitHub Actions 执行、systemd/Nginx 实际运行、SSH 发布和真实邮件投递必须在目标环境单独验收。任务日志状态不代替邮件供应商或收件箱的最终送达证据。
