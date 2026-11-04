# React + FastAPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 未获用户明确委派授权，不启用子代理。

**Goal:** 按已确认业务范围交付个人使用的组件化订阅后台。

**Architecture:** React 前端通过同源 `/api/` 访问 FastAPI；后端管理业务规则及 SQLite 数据，服务器 systemd timer 执行提醒。一个仓库、一个域名、GitHub Actions 经 SSH 原生部署。

**Tech Stack:** React、Vite、TypeScript、React Router、TanStack Query、FastAPI + Pydantic 2 + SQLAlchemy 2 + Alembic + Uvicorn、SQLite、pytest、Playwright。依赖在实施时核实兼容版本并锁定，不把本文当作版本最新性声明。

**Spec:** `docs/superpowers/specs/2026-10-16-ai-subscription-management-design.md`。

本计划替代旧框架实施步骤。2026-10-16 计划仅保留实体字段、业务函数及验收场景作为业务契约，ORM、测试客户端、迁移、管理命令等框架代码全部按本文件实现；部署采用 `2026-10-16-native-cicd-deployment.md`。本文件为当前实施入口，部署修订提供发布规则；旧计划中的 Django 模板描述及框架特有测试不再执行。

## Global Constraints

- 个人使用，中文界面，人民币分存储，Asia/Hong_Kong 时区。
- 手动录入上游；同客户多项服务；日周月年期限；提前 3 天及当天提醒。
- 第一版不做客户门户、自动交付、付款、上游额度查询或自动微信消息。
- React + Vite + TypeScript、FastAPI API、SQLite；不使用 Docker Compose。
- 开发阶段可使用 Vite 代理；生产网页与 `/api/` 同域，同一服务器。
- 真实服务器发布及邮件投递依赖可用配置；不能以模拟结果替代线上验收。

## Review Focus

1. 未登录 API 返回 401 JSON，前端回登录页，不能误把 HTML 当业务数据。
2. Session cookie 登录必须配合 CSRF，登录、退出及其他写操作均受保护。
3. SQLite 独立连接并发与重复提交不能重复续费，SMTP 网络调用不持有写事务。
4. 前端金额及日期预览不作为权威值，服务器重新验证。
5. 发布时旧网页缓存、失败请求、数据库文件与生产配置不能导致数据被覆盖。

## 文件与责任

```text
frontend/package.json、package-lock.json、vite.config.ts、tsconfig.json
frontend/src/app/router.tsx、providers.tsx、AppLayout.tsx
frontend/src/api/client.ts、types.ts
frontend/src/components/{MoneyInput,StatusBadge,ContactList,ConfirmDialog}.tsx
frontend/src/features/auth/{api,LoginPage}.tsx
frontend/src/features/customers/{api,CustomerList,CustomerDetail,CustomerForm}.tsx
frontend/src/features/catalog/{api,SupplierList,SupplierForm,ProductList,ProductForm}.tsx
frontend/src/features/billing/{api,SaleForm,ServiceDetail,SaleHistory}.tsx
frontend/src/features/dashboard/{api,DashboardPage}.tsx
frontend/src/features/reminders/{api,ReminderSettings,ReminderLog}.tsx
frontend/src/styles/app.css
backend/pyproject.toml、requirements.lock、alembic.ini
backend/app/{main,config,db,errors,cli}.py
backend/app/{accounts,crm,catalog,billing,reminders}/
backend/alembic/env.py、versions/
backend/tests/                     原计划各后端测试迁入这里
frontend/tests/e2e/owner-flow.spec.ts
.github/workflows/{ci,deploy}.yml
ops/deploy.sh、ops/systemd/*、ops/nginx.conf、ops/{backup,restore}.py
```

所有前端组件文件为 tsx；纯请求函数和纯类型文件为 ts。api 占位路径在实现时使用 api.ts，而非无 JSX 的 api.tsx。不为每个输入框设计通用表单引擎，先按业务做清晰组件。

## API 契约

- `GET /api/auth/csrf/`：设置 CSRF cookie，JSON 返回 csrfToken；前端请求头 `X-CSRFToken`，fetch credentials 使用 same-origin。
- `POST /api/auth/login/`：用户名密码，成功返回 `{user:{id,username}}`；错误密码 400；CSRF 失败 403。
- `GET /api/auth/me/`：返回 user；未登录 401。`POST /api/auth/logout/`：204。
- `/api/customers/`、`/api/suppliers/`、`/api/products/`：GET/POST；`/<id>/` GET/PATCH；归档、停用及删除遵守原设计引用规则，写操作要求 CSRF。
- `/api/services/` GET；`/<id>/` GET；`/<id>/renew/`、`topup/`、`end/` 为 POST。
- `/api/sales/` GET/POST；`/<id>/` GET；`/<id>/correct/`、`void/` POST。
- `GET /api/dashboard/?month=2026-10`：返回统计及待办；`GET /api/sales/` 支持原计划过滤参数。
- `/api/reminders/settings/` GET/PATCH；`/api/reminders/runs/` GET；`test/`、`retry/` POST。
- 列表结构 `{count,next,previous,results}`，每页 25 条；日期 YYYY-MM-DD；金额整数分，额度十进制字符串。
- 错误结构 `{code,message,fields}`；服务 revision 冲突 409，提交 UUID 重放同内容返回原交易，不重复变更。
- 单管理员 Cookie 会话登录：密码以 Argon2 哈希保存，随机会话 token 仅哈希入库，Cookie 生产配置 Secure/HttpOnly/SameSite=Lax。匿名 CSRF 入口创建短期预登录会话，绑定 CSRF token；登录验证 token 后轮换会话 ID 和 CSRF token，所有写接口检查会话绑定的 token 及同源 Origin，退出使会话立即失效。前端不把会话 token 放 localStorage，生产不启用跨域凭据访问。
- 原计划可选 HTTP 定时任务入口取消；第一版只用服务器命令行任务，减少对公网暴露的入口。

## Task A：登录与前后端运行骨架（覆盖原任务 1）

**Files:** frontend 配置、api/client.ts、features/auth/*、app/*；backend/app/{main,config,db,errors,cli}.py、accounts/*、tests/test_auth.py。

**Interfaces:** `request<T>(path:string, init?:RequestInit):Promise<T>` 统一解析错误；TanStack Query 管理服务器数据；React Router 负责页面路由；未登录数据清空并回登录页。

- [x] 建立 frontend/backend 目录、Python 虚拟环境、npm 及 Python 锁文件，SQLite 数据文件写入忽略目录。HTTP 测试使用 FastAPI TestClient 和临时磁盘数据库，SQLAlchemy Session 每请求创建、关闭；fixture 覆盖数据库依赖，不连接真实业务数据库。设置 Vite `/api/` 代理至本地 FastAPI。
- [x] 编写并先运行失败的后端安全测试：

```python
def test_private_api_is_json_401(client):
    response = client.get('/api/customers/')
    assert response.status_code == 401
    assert response.json()['code'] == 'unauthenticated'

def test_login_csrf_required(client):
    response = client.post('/api/auth/login/', json={
        'username': 'owner', 'password': 'example-test-password'
    })
    assert response.status_code == 403
```

- [x] 实现会话、CSRF、唯一经营者初始化命令 `python -m app.cli bootstrap-owner` 及前端登录页；请求层正确处理 204，无内容响应不调用 JSON 解析。
- [x] 加退出清空 query cache、401 重定向、登录节流及外部重定向拒绝用例；后端 auth 测试通过。
- [x] 执行前端 `npm run typecheck`、`npm run build`；浏览器验证登录与退出；提交登录骨架。

## Task B：数据规则与档案管理（覆盖原任务 2、3）

**Files:** backend/app/crm、catalog、billing 数据模型、日期金额函数；对应 schemas.py、router.py；frontend/components/*、features/customers/*、features/catalog/*。

**Interfaces:** 使用原计划实体字段及纯函数契约；模型使用 SQLAlchemy DeclarativeBase，外键启用 foreign_keys=ON，删除保护由 FK RESTRICT 和服务校验实现，Pydantic schema 负责 API 字段验证，业务函数负责跨模型变更；MoneyInput 字符串输入转整数分，拒绝超过两位小数。

- [x] 先运行原日期金额用例至失败，实现数据模型、SQLite 约束及 Alembic 迁移（`alembic upgrade head`）；日期月底、闰年、无期限额度均覆盖。
- [x] 编写 API 新增客户带微信和 QQ 的集成测试，断言 201 及读取返回两条联系方式；实现联系方式整组修改的原子保存。
- [x] 实现渠道和商品 API，以及客户、商品、渠道列表和表单；前端只从 api.ts 调用接口，组件不直接拼数据库字段请求。
- [x] 测试报价更改不改历史、引用保护、网址 http/https 校验和恶意备注转义；完成归档确认交互。
- [x] 执行对应后端测试与前端类型检查、构建，提交档案管理。

## Task C：购买、续费与利润（覆盖原任务 4、5）

**Files:** backend/app/billing/services.py、queries.py、schemas.py、router.py；frontend/features/billing/*、dashboard/*。

**Interfaces:** 保留原 SaleInput 及 purchase/renew/topup/correct_sale/void_sale/end_service/month_totals 签名；API 将输入转换为 SaleInput，revision 与 submission_id 显式传入。

- [x] 原计划重复购买、独立续费、提前与逾期续费、成交快照、负利润测试先失败；使用磁盘 SQLite 独立连接验证，不以无效行锁代替并发保护。
- [x] 使用短事务及 revision 条件更新，失败整笔回滚；SQLite 写入锁忙有界重试，超过上限返回可重试错误，不保留部分交易。
- [x] 实现购买与续费 API、可复用 SaleForm、交易历史、单服务详情；冲突 409 保留输入并提示重新读取服务状态，不能静默自动重提续费。
- [x] 实现首页及筛选、人民币分聚合；前端发起 mutation 成功后失效关联客户、服务、交易、首页缓存。
- [x] 编写浏览器关键断言并执行：

```typescript
import { test, expect } from '@playwright/test';
test('首页显示差价利润', async ({ page }) => {
  // 测试配置预先加载独立数据库演示数据与管理员 storageState。
  await page.goto('/');
  await expect(page.getByText('本月差价利润', {exact:true})).toBeVisible();
});
```

- [x] 原作废与纠错验收、前端构建及浏览器流程通过后提交。

## Task D：到期邮件及自适应验收（覆盖原任务 6、7、8 界面部分）

**Files:** backend/app/reminders/*、tests/test_reminder*；frontend/features/reminders/*、styles/app.css；frontend/tests/e2e/owner-flow.spec.ts。

**Interfaces:** 保留 plan_due/send_due/run_cycle/send_digest；服务端命令 `python -m app.cli run-reminders` 为唯一生产调度入口。

- [x] 提醒日期、漏发恢复、历史补录排除、旧节点取消、重复任务的后端测试先失败，再实现 planner。
- [x] 实现状态条件认领与租约、SMTP 发送、结果不确定状态及重试；发信在写事务外，发送前检查当前服务；接受已启动网络投递不能撤回的明确限制。
- [x] 完成接收邮箱设置、测试邮件及发送日志 API 和 React 页面，不向浏览器返回 SMTP 凭据。
- [x] 以 390px 与桌面宽度验证建渠道→商品→客户→两项服务→单项续费→利润→到期提醒日志；无横向页面溢出，失败和空数据状态可理解。
- [x] 运行完整后端用例、前端类型检查、生产构建及 Playwright；提交提醒与完整流程。

## Task E：GitHub CI/CD 原生发布（覆盖原任务 8 部署部分）

**Files:** .github/workflows/*、ops/*、README.md、docs/deployment.md。

**Interfaces:** 发布产物为前端 dist 和后端源代码及锁文件，数据保存于服务器 shared 目录。具体发布分支以用户仓库为准，默认 main。

- [ ] CI 使用独立测试数据库，执行后端测试、`alembic check` 和迁移升级检查、前端类型检查、构建及浏览器关键流程；失败不能触发生产发布。
- [ ] Nginx 提供前端 dist、SPA 页面回退及 FastAPI `/api/` 转发；API 错误不能回退到 index.html。index.html 不长缓存，带内容哈希资源可长缓存。
- [ ] 按部署修订执行 SSH host key 校验、发布串行锁、release 准备、停止写入、备份、迁移、版本切换和健康检查；启用应用服务、提醒 timer 和备份任务。
- [ ] 测试备份 integrity_check、隔离恢复、重复发布及兼容 schema 回滚；生产凭据不进入产物。
- [ ] 未收到服务器信息前完成本地及工作流文件验证；获得配置后再执行真实发布并验证邮件，不提前宣称上线。

## 执行状态（2026-10-17）

A 至 D 已实现并通过本地验证。E 的工作流、配置、脚本及部署文档已交付，备份恢复通过实际测试；真实服务器发布、远程回滚、GitHub Actions 运行与 SMTP 投递在配置目标环境后验收，相关复选项不提前标完成。

## 自审与交接

业务范围及原 14 项验收不变；前端替换有明确文件与 API 契约；移除公网任务入口、PostgreSQL 专用并发方案与容器步骤。API 和页面测试替代原 Django 模板响应测试。执行推荐主助手在当前会话顺序开发，无需用户提前提供服务器密码，部署参数在部署阶段再落实。用户已明确授权切换 FastAPI；当前完成计划变更，产品实现按更新后的计划执行。

## FastAPI 专项实施约定

- 使用同步 SQLAlchemy Session 和同步 `def` 业务路由，首版不引入异步数据库引擎。请求数据库依赖只负责创建与关闭 Session，事务由业务服务显式控制，读取认证信息后的隐式事务需先结束，不能把发信或用户交互置于写事务中。
- 统一 ApiError(code, message, fields) 及 Pydantic 验证错误处理器；未登录 401、CSRF 403、字段错误 422、revision 冲突 409。修改前先对 API 契约测试，前端按稳定错误结构处理。
- Session 表：token_hash、csrf_token_hash、owner_id（预登录可空）、expires_at、created_at；Owner 只有一条记录，数据库固定主键 1 保证唯一。失败登录限流数据跨请求持久化，默认运行一个 Uvicorn worker，初始部署不启用公开注册。
- SQLite 为每个连接启用 foreign_keys 和 busy_timeout；WAL 在数据库初始化时配置。金额用带 CHECK 的整数分，额度在 SQLite 中以规范十进制字符串保存并由 Decimal 精确计算，不能默认依赖 NUMERIC 的浮点转换保持精度。
- 写事务以明确的 BEGIN IMMEDIATE 路径运行，事务内检查 revision、写入交易与更新服务；锁忙最多重试 3 次，超时返回 503。幂等 UUID 与提交内容摘要一起保存，同 UUID 不同内容返回 409。会话不跨线程共用。
- SMTP 用 Python smtplib + EmailMessage；开发提供捕获邮件的测试适配器，生产连接超时 10 秒、TLS/SSL、错误脱敏。提醒数据状态由数据库持久化，不用 FastAPI BackgroundTasks 代替服务器定时调度。
- 命令行模块 app.cli 提供 bootstrap-owner、run-reminders、backup；CLI 与 API 共用业务服务，互不依赖运行中的 HTTP 服务。备份底层使用 SQLite Backup API。
- Alembic 为 SQLite 的表结构修改提供 batch migration，生产禁止每次启动通过 create_all 自动修改 schema。CI 从空库升级到 head，审查自动生成迁移，并验证一个现有测试库升级后历史记录仍在。
- 生产启动 `uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1`，由 systemd 管理；开发可额外使用 --reload。只信任实际反向代理地址，健康接口不包含客户数据；生产 OpenAPI 文档关闭或要求登录。

## 当前检查命令

从 backend 目录、已激活虚拟环境执行：

```text
python -m pytest -q
alembic upgrade head
alembic check
python -m app.cli --help
```

从 frontend 目录执行：

```text
npm ci
npm run typecheck
npm run build
npx playwright test
```

迁移和测试一律用专用临时数据库。登录测试的 client fixture 为 TestClient；金额和日期纯函数测试去除 pytest-django 标记；数据库集成用例用 SQLAlchemy fixture，不使用 Django ORM 查询。原接口响应中的 results 分页结构由本项目 schemas 实现，不引入第二套框架。

## 技术参考（执行时核实版本并锁定）

```text
https://fastapi.tiangolo.com/tutorial/sql-databases/
https://fastapi.tiangolo.com/deployment/manually/
https://docs.sqlalchemy.org/en/20/dialects/sqlite.html
https://alembic.sqlalchemy.org/en/latest/batch.html
```
