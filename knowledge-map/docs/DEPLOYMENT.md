# 发布到自己的服务器

## 当前实际部署（2026-09-10）

- 访问：`https://121.41.92.58:18443`，用户名 `zhixu`，密码由用户在服务器终端设置。
- 服务器：Ubuntu 24.04，沿用 Nginx；不覆盖端口 80 和 18181 的已有站点。
- 配置：`deploy/nginx-ip.conf`；服务器 `/etc/nginx/sites-available/zhixu-ip`。
- 证书：复用 `/etc/letsencrypt/live/ai-prompt-optimizer-ip/` 的 IP 证书。现有 Certbot timer 和 deploy hook 负责续期及 Nginx 重载，不删除原证书 lineage 或其续期配置。
- GitHub：私有仓库 `HP-Patience/knowledge-map`，`production` 环境仅允许 main 分支；5 个部署 Secret 已配置。
- 部署账号：`zhixu-deploy`，无 sudo/docker 权限，不能读取网页登录密码文件。专用 SSH 公钥带 restrict，禁止端口转发和 PTY。
- CI 私钥位于 GitHub Environment Secret；本机副本位于被 Git 忽略、限制 ACL 的 `.local/deployment/`。不要输出或提交该目录。
- SSH 端口是 **22**，网站端口是 **18443**，两者不要混用。

首次安装脚本 `deploy/setup-nginx-ip.sh` 只供空目录初始化，已有站点不要重复执行。`deploy/install-ci-key.sh` 用于追加部署公钥，不覆盖原有 authorized_keys。后续更新直接由 Actions 上传已校验的 release，并原子切换 current，不需要每次重载 Nginx。

密码修改应在管理员终端交互完成，保留 `/etc/nginx/zhixu.htpasswd` 的 root:www-data、640 权限。不要在聊天、命令参数、GitHub Secrets 或前端写入网页登录密码。

下面 Caddy 章节保留为另一台空白服务器的替代部署方案，**不是当前 Nginx 服务器的重复安装指令**。

## 替代部署方案：Caddy

### 状态与约定

当前已有 Nginx 站点；若另部署新服务器，以下以 **Linux + systemd + Caddy** 为默认部署方案；若服务器已使用 Nginx 等入口，应先检查现有站点，不要直接覆盖配置或抢占 80/443 端口。

- 一个私有仓库，发布分支 `main`。
- 电脑本地生成 `release/`，与对应数据和源码一起提交。
- Actions 只验证并上传已有产物，绝不自动重建来掩盖忘记本地构建的问题。
- `/srv/zhixu/current` 指向当前静态目录；`releases/<版本>` 保留旧资源和回滚版本。
- 正式站点用域名根路径，不支持未经配置的子路径挂载。
- 仅发布静态文件，不把项目仓库整个上传到 Web 根目录。

## 1. 一次性准备服务器

需要域名 A/AAAA 指向服务器、可用的 80/443 端口、Python 3.9+、Caddy 2（支持 `basic_auth`）。请通过 Caddy 官方安装方式安装并管理服务。服务执行用户以下假设为 `caddy`。

管理员创建普通部署账号 `zhixu-deploy`。该账号不加入 sudo，不用于运行 Caddy。将 GitHub 部署专用公钥加入它的 `~/.ssh/authorized_keys`，建议加 `restrict` 前缀，禁止端口转发和交互终端；SSH 文件权限按常规最小权限设置。

```sh
sudo install -d -o zhixu-deploy -g caddy -m 755 /srv/zhixu
sudo install -d -o zhixu-deploy -g caddy -m 700 /srv/zhixu/incoming
sudo install -d -o zhixu-deploy -g caddy -m 755 /srv/zhixu/releases
sudo install -d -o root -g root -m 755 /opt/zhixu
# 将项目中的脚本安全复制到服务器后，由管理员安装：
sudo install -o root -g root -m 755 activate.py /opt/zhixu/activate.py
```

`activate.py` 为管理员维护脚本，Actions 不自动覆盖它。升级部署协议时先更新该脚本，再发布新产物。部署用户只能写专用站点目录，不能修改 Caddy 认证文件。incoming、releases 和 current 必须位于同一文件系统，保证目录移动/软链接切换的原子性。

## 2. HTTPS 和全站密码

1. 运行 `caddy hash-password`，交互输入一个唯一强密码，获得密码哈希。不要把明文放命令行、聊天或提交进 Git。
2. 在服务器创建 `/etc/caddy/zhixu.env`（root 拥有，权限 600）：

```ini
ATLAS_DOMAIN=map.your-domain.example
ATLAS_USER=your-private-username
ATLAS_PASSWORD_HASH=替换为caddy生成的哈希
```

3. 使用 `sudo systemctl edit caddy` 添加：

```ini
[Service]
EnvironmentFile=/etc/caddy/zhixu.env
```

4. 将项目 `deploy/Caddyfile` 中的站点块合并进服务器 Caddy 配置。不要覆盖现有其他站点。
5. 在加载上述环境变量的管理员环境中先执行 `caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile`。确认通过后 `sudo systemctl daemon-reload`、`sudo systemctl restart caddy`。环境变量或密码变化需要重启进程，使新的环境生效。

Caddy 管理域名 HTTPS 证书；DNS、端口或已有代理不匹配会导致证书申请失败，需要现场排查。不要用浏览器忽略证书警告替代 HTTPS 验证。

**保护范围包括首页、带哈希的 JSON、JS/CSS、所有旧版本目录。** 静态服务没有另一个裸端口。不要在 0.0.0.0 上运行开发服务器、`vite preview` 或 Python 静态服务。防火墙仅开放必需的 HTTPS/HTTP 与受限 SSH。

Basic Auth 使用浏览器原生弹窗，不提供注册/找回密码/可靠退出按钮。浏览器可能在当前会话记住凭据，公共电脑上不建议使用。退出可关闭相关浏览会话；需要撤销访问时在服务器更换密码并重启 Caddy。

所有响应设置 `private, no-store`，不使用 Service Worker 或 localStorage 缓存知识。认证不是端到端加密：已授权设备仍能读取内容，GitHub 私有仓库和构建历史也持有知识数据。

## 3. GitHub 配置

先创建并连接你自己的 **私有仓库**，确认默认/发布分支为 `main`。本项目不替你创建公开仓库或假定远程地址。

仓库设置中创建 `production` Environment，限制部署分支为 main；如果账号套餐支持，可启用人工审批。配置以下 Environment Secrets：

| Secret | 内容 |
|---|---|
| `DEPLOY_HOST` | 服务器域名或 IPv4 地址，不含协议/路径；当前脚本不接受 IPv6 字面值 |
| `DEPLOY_PORT` | SSH 端口，不填默认 22 |
| `DEPLOY_USER` | 普通部署用户名，如 zhixu-deploy |
| `DEPLOY_SSH_KEY` | 该站点专用 SSH 私钥，不是账号主密钥 |
| `DEPLOY_KNOWN_HOSTS` | 已经通过可信渠道核对指纹的 known_hosts 记录；非 22 端口用 `[host]:port` 格式 |

不要在 workflow 中运行未核验的 `ssh-keyscan` 然后直接信任，也不要关闭 StrictHostKeyChecking。首次服务器指纹从服务商控制台或现有可信 SSH 会话核验。**网页登录密码和哈希不放 GitHub Secrets，也不进入前端。**

建议启用 main 分支保护，要求 Verify 检查、评审部署脚本和 workflow 变更。不使用 `pull_request_target` 执行外部 PR 代码。部署 Secret 只在验证成功的部署 job 中使用。供应链有更严格要求时，可将 Action 版本标签更新为经核验的完整提交 SHA。

## 4. 每次发布

```sh
npm ci
npm run check
npx playwright install chromium
npm run test:e2e
npm run build
npm run verify:release
# 然后检查 git diff，将源码、data 和 release 一起提交，再推送 main。
```

不要手改 `release/manifest.json` 修复验证错误。应重新构建。`.gitattributes` 保证产物字节不被 Git 换行转换；源文本指纹则规范化换行，兼容 Windows 开发、Linux 验证。

Actions：验证类型/知识/测试/产物 → 上传已验证 artifact → 固定 SSH 主机密钥上传独立 incoming 目录 → 服务端再次核对文件清单、哈希、版本路径 → 切换 current。上传或验证失败不会先删除旧站点。

运行编号和重试次数防止落后的 workflow 覆盖较新发布。同一 run 的重试使用新的目录。同一构建版本可幂等发布，但内容不同却重用版本号会被拒绝。workflow 文件/仓库迁移导致编号重置时，需要管理员理解现有状态后迁移 `last-run.json`，不要盲删来绕过校验。

Actions 成功表示产物验证和服务器激活成功；公网 DNS、证书、密码可用性还应按下面的清单确认。当前模板不会将网页登录密码交给 CI 做浏览器登录。

## 5. 上线安全验收（必须在真实域名检查）

用浏览器隐私窗口确认未登录无法查看。用 curl 检查：

```sh
curl -I https://你的域名/
curl -I https://你的域名/versions/实际版本/assets/实际JSON文件名.json
curl -I https://你的域名/versions/实际版本/assets/实际JS文件名.js
# 以上应为 401，不返回知识内容。

curl -I -u 错误用户名:错误密码 https://你的域名/
# 仍应为 401。

curl -I -u 你的用户名 https://你的域名/
# curl 交互询问密码，正确后应为 200。
```

还要检查：HTTP 仅跳转 HTTPS；可信证书；旧版本资源同样 401；`.git/config`、`AGENTS.md`、`.local/` 不能读出真实项目文件；服务器 IP/备用域名/其他端口没有绕过认证的入口；手机和平板可以正确登录。使用实际 manifest 中的资源名，不要只检查首页。

## 6. 回滚与历史

先在服务器查看当前和前一版 `readlink /srv/zhixu/current` / `readlink /srv/zhixu/previous`，再选择要恢复的版本：

```sh
python3 /opt/zhixu/activate.py rollback 20260910000000-aaaaaaaaaa
```

示例版本号需替换为真实 `releases/` 内版本。脚本先校验旧版本完整性，再原子切换；不回退防旧任务覆盖的流水号。回滚不会修改本地知识源或 Git，请另外决定是否恢复数据并发布修正版。

不自动删除旧版本，避免已打开页面的版本化资源丢失。长期使用需监控磁盘并规划保留期；手工清理前确保不是 current/previous 指向的版本，也接受旧页面必须刷新。GitHub 历史、备份和旧发布可能保留已删除的私人内容，彻底删除敏感数据需分别处理。

## 7. 常见问题

- **知识校验失败**：根据错误检查 ID、引用、时间、循环；用本机备份恢复。不要跳过验证。
- **源文件与产物不一致**：修改数据/代码后重新本地 build，提交完整 release。
- **SSH 主机验证失败**：先通过可信渠道核验服务器是否变更，再更新 Secret。
- **403 / 文件权限错误**：Caddy 需要遍历 /srv/zhixu 和 releases 并读取静态文件；不要授予写权限解决读权限问题。
- **资源 404**：检查版本化路径、Caddy `handle_path /versions/*` 和 releases 的实际版本；不要把所有资源请求回退成 HTML；本项目没有需要 SPA fallback 的前端路径路由。
- **回滚测试在 Windows 报 1314**：原子部署目标是 Linux，使用 WSL 运行部署测试，不必为测试提高 Windows 系统权限。
- **Actions 未执行**：确认 workflow 已推送、Actions 已启用、分支为 main、Environment 配置完整。
