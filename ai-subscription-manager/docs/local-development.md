# 续订 · AI 订阅管理工作台

个人使用的中文管理后台：手动维护上游渠道、自定义商品和客户，记录购买与续费，统计人民币差价利润，并通过邮件提醒经营者联系客户。

## 技术结构

- `frontend/`：React、Vite、TypeScript、React Router、TanStack Query。
- `backend/`：FastAPI、Pydantic、SQLAlchemy、Alembic、SQLite。
- `ops/`：原生 Linux/systemd/Nginx 部署、提醒调度及数据库备份脚本。
- `.github/workflows/`：测试、构建、GitHub Actions 经 SSH 发布。

不需要 Docker。前后端同仓库；生产同域，`/api/` 由后端处理，数据库保存在发布目录以外。

## Windows 本地启动

需要 Python 3.12 和 Node.js 22。以下 PowerShell 命令从仓库根目录执行：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.lock
Copy-Item .env.example backend/.env
Set-Location backend
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开终端，在仓库根目录运行：

```powershell
Set-Location frontend
npm ci
npm run dev
```

浏览器访问 `http://localhost:5173`。APP_APP_URL 必须与实际访问来源一致（包括 localhost/127.0.0.1 和端口）；跨来源的写请求会被拒绝。首次打开网页会显示“设置管理员账户”：填写用户名、密码并再次确认，即创建唯一管理员并自动登录。创建完成后只显示登录页，不能再次注册或覆盖管理员。密码至少 12 位，不存在默认账号密码；命令行 bootstrap-owner 仍保留为可选初始化方式。

开发时如需样例，在空业务数据库、非生产环境执行 `python -m app.cli seed-demo`。种子明确标注演示客户与渠道，不是实际供货建议。本机预览已改为首次网页设置管理员，已有演示客户和交易会保留。请使用你自己在首次设置时填写的账号密码登录。

## 使用流程

1. 新增上游渠道和商品，填写参考价格、交付方式、期限及可选额度。
2. 新增客户，保存微信、QQ、电话或邮箱等联系方式。
3. 从客户详情记录购买，核对实际成本、售价及服务期限。
4. 每个客户可有多个服务，甚至同套餐多个账号，各自独立到期。
5. 从服务详情续费或追加额度；每次产生独立交易。采购报价变化不修改历史交易。
6. 在邮件提醒页保存接收邮箱；服务器 SMTP 配好后发送测试邮件。

日/周按天数相加，月/年按日历计算并处理月末。提前续费从原到期日继续，逾期续费默认从成交日期开始。手动到期日优先。无期限额度不生成到期提醒，累计购买量不代表剩余额度。

金额以分保存；差价利润是销售金额减采购成本，并非扣除全部经营费用的净利润。纠错和作废必须明确确认当前服务状态，不会静默撤销后续续费。

## 测试与构建

```powershell
backend/.venv/Scripts/python -m pytest backend/tests -q
Set-Location backend
.venv/Scripts/python -m alembic check
Set-Location ../frontend
npm run typecheck
npm run build
npx playwright test
```

浏览器测试创建独立 `.local/e2e-*.db`，使用专用测试账户，不连接本地预览或生产数据库。Windows 默认使用本机 Chrome；Linux CI 先执行 `npx playwright install --with-deps chromium`。通过 E2E_PYTHON 可指定后端 Python 路径。浏览器验收截图在 `artifacts/`（忽略提交）。

## 邮件与部署

参见 [部署说明](deployment.md)。邮箱接收地址在后台设置；SMTP 凭据只在服务器环境文件中设置。默认邮件后端 disabled，保存客户与交易不依赖 SMTP。

提醒计划：香港时区每天 09:00 汇总到期前 3 天及当天的服务，服务器每 15 分钟扫描并重试有效漏项。SMTP 超时可能实际已投递，日志记录“结果待核实”，再次重试存在重复邮件的可能。停止生成提醒不代表能撤回已经发出的邮件。

当前 GitHub 工作流、服务器配置为待部署文件。没有服务器/SMTP 凭据时，不代表已在线运行或已经验证真实投递。
