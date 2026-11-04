# AI Subscription Management Implementation Plan

> 2026-10-17：框架方案已被 `2026-10-17-react-fastapi-implementation.md` 替代。本文件仅作历史与业务规则参考，不执行旧框架步骤。

> 2026-10-17 更新：前后端技术方案以 `2026-10-17-react-django-plan-amendment.md` 为准；本文件保留业务契约与测试规则。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task by default. If the user explicitly chooses delegation, use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**部署修订（2026-10-16）：** 用户已明确不使用 Docker Compose，采用 GitHub CI/CD 更新服务器。以同目录 `2026-10-16-native-cicd-deployment.md` 为部署实施依据。本文原有容器、本地数据库容器、PostgreSQL 专用锁和备份步骤停止执行。Django/SQLite 是当前建议，Rust 尚未被选定；语言和数据库确认后再修订相应代码任务，不能将本次部署确认视为全部实施计划获批。

**Goal:** 交付个人使用的中文网页后台，管理上游、商品、客户、购买续费、人民币利润及两次到期邮件提醒。

**Architecture:** 单体网页应用，服务器直接运行应用进程，由 systemd 管理；systemd timer 每 15 分钟执行提醒任务。当前技术建议为 Django 模板页面及 SQLite，交易和提醒写入使用短事务、唯一约束及条件更新；不能依赖 PostgreSQL 行锁或在数据库写事务中执行邮件网络请求。

**Tech Stack（建议，待确认）:** Python 3.12、Django 5.2 LTS、SQLite、原生 CSS 和少量 JavaScript、pytest/pytest-django、Playwright。GitHub Actions 执行 CI/CD，经 SSH 发布至 Linux 服务器，Gunicorn 配合 systemd 运行，Nginx 提供 HTTPS 入口。依赖提交精确锁文件；邮件使用 SMTP，开发测试使用内存后端。Rust 仍是备选，不因本修订被默认否决。

**Spec:** `docs/superpowers/specs/2026-10-16-ai-subscription-management-design.md`（用户已于 2026-10-16 确认）。

## Global Constraints

- 只有经营者自己登录后台，客户没有登录入口。
- 第一版由经营者手动搜集、录入上游渠道，不自动搜索渠道。
- 订阅期限支持日、周、月、年及对应数量。
- 到期前 3 天提醒一次，到期当天提醒一次，邮件发给经营者，由经营者联系客户。
- 全部按人民币记账。
- 同一个客户可以同时购买多项服务，各项到期时间独立。
- 所有日期、每日统计和提醒任务使用 Asia/Hong_Kong 时区。
- 金额以人民币分存储；会员使用期与质保条件分别记录；无有效期额度服务不提醒。
- 不保存交付账号密码、2FA 秘钥或 API 密钥；服务器运行凭据不得写入仓库或返回浏览器。
- 本计划仅安排开发及部署准备；不购买服务器、不创建付费服务、不发送客户消息。
- 工作区目前只有设计文档及 Git。编写产品代码前完成计划审阅；执行阶段按 using-git-worktrees 技能处理隔离工作区。

## Review Focus

1. 浏览器重复提交购买或续费：同一个提交标识只产生一笔交易和一次期限变更，任务 4 验证。
2. 用户打开旧表单后他处续费或改价：旧服务版本不能覆盖新期限，实际金额以本次明确提交为准，任务 4 验证。
3. 定时任务停机跨越提醒日：恢复时补发有效漏项，但后录入历史服务不生成录入前提醒，任务 6 验证。
4. 恶意备注或外站链接：模板转义文字、网址只接受 http/https、任何写操作必须通过 CSRF，任务 3 和 8 验证。
5. 邮件已投递但响应超时或进程退出：标记投递结果不确定且保留批次标识，界面解释可能重复，不虚报成功，任务 7 验证。

---

## 技术依据与执行环境

本机已有 Python 3.12.10 和 Node.js；本地运行及测试不依赖容器引擎。生产按 Linux + systemd + HTTPS 入口设计，具体发行版、CPU 架构和运行时在服务器信息明确后设置。数据库使用持久目录；当前建议 SQLite，相关并发任务按下述修订执行。

技术依据包括 Django 数据库事务、SQLite 限制及邮件文档；部署参考 GitHub Actions 文档，备份参考 SQLite Backup API。下面文档链接用于执行时复核，不代表原 PostgreSQL 行锁步骤仍可使用。

```text
https://docs.djangoproject.com/en/5.2/releases/5.2/
https://docs.djangoproject.com/en/5.2/topics/db/transactions/
https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update
https://docs.djangoproject.com/en/5.2/topics/email/
```

## 文件责任地图

```text
manage.py                         Django 命令入口
pyproject.toml / requirements.lock Python 依赖、测试配置及精确版本
config/settings.py                时区、数据库、会话、邮件及安全配置
config/urls.py / wsgi.py           路由总入口与生产服务器入口
accounts/views.py / urls.py       仅经营者登录、退出
accounts/management/commands/bootstrap_owner.py 交互式创建唯一经营者
crm/models.py / forms.py / views.py / urls.py    客户与联系方式
catalog/models.py / forms.py / views.py / urls.py 上游渠道与商品
billing/models.py / inputs.py      服务、交易、成交快照、输入结构
billing/dates.py / money.py        纯日期与金额运算
billing/services.py               购买、续费、编辑、作废及结束服务事务
billing/queries.py / forms.py / views.py / urls.py 查询、报表与交易页面
reminders/models.py               提醒项目、发送批次、任务运行记录
reminders/planner.py / sender.py   漏项生成、失效检查、分批发送及重试
reminders/mail.py                  SMTP 适配、测试邮件及错误脱敏
reminders/forms.py / views.py / urls.py 设置、日志、受保护任务入口
reminders/management/commands/run_reminders.py 任务命令行入口
templates/base.html / accounts/ / crm/ / catalog/ / billing/ / reminders/
static/app.css / app.js           自适应界面和表单辅助交互
*/migrations/                     对应模块数据库迁移
tests/conftest.py                 Django 登录、数据库和数据工厂 fixture
tests/test_auth.py                登录及未授权保护
tests/test_catalog_crm.py         客户与上游商品行为
tests/test_dates_money.py         金额、月末闰年及日期边界
tests/test_billing.py             交易历史、续费、作废、重复提交
tests/test_reminder_planner.py    提醒计划及恢复
tests/test_reminder_sender.py     发送重试、并发及过期项目排除
tests/test_dashboard.py           报表、过滤及有效状态
tests/e2e/test_owner_flow.py       浏览器完整流程及手机检查
.github/workflows/ci.yml / deploy.yml   自动测试及发布流程
ops/deploy.sh / systemd/* / nginx.conf   原生部署、应用和提醒服务
ops/backup.py / restore.py               数据库一致性备份及测试恢复
docs/superpowers/plans/2026-10-16-native-cicd-deployment.md 部署修订与验收
.env.example / .gitignore / README.md / docs/deployment.md 运行说明
```

路径均相对于仓库根目录。任务默认在工作区虚拟环境激活后执行命令；PowerShell 激活为 `.venv\Scripts\Activate.ps1`。每个任务的测试先失败再实现并通过，提交时只暂存该任务实际文件。

## 固定的数据和接口契约

- `Customer`：name、notes、archived_at、created_at、updated_at；`Contact`：customer、kind、value。
- `Supplier`：name、url、contact_name、contact_details、notes、is_active。
- `Product`：supplier、name、platform、plan、delivery、source_name、source_url、tags（JSON 字符串数组）、cost_fen、price_fen、quoted_on、term_count/term_unit（均可空）、quota_amount/quota_unit（均可空）、warranty_notes、is_active。
- `Service`：customer、product、identifier、started_on、expires_on（可空）、quota_unit、purchased_quota、notes、ended_at、revision（整数）、created_at、updated_at。`purchased_quota` 仅为累计购买量。
- `Sale`：customer、service、product、kind（purchase/renewal/topup）、sold_on、cost_fen、price_fen、snapshot（JSON）、before_state/after_state（JSON）、submission_id（UUID 唯一）、voided_at、void_reason、created_at、updated_at。快照保存当次客户名、渠道名、商品描述、期限与额度；原关联使用 PROTECT。
- `Reminder`：service、target_expiry、kind（before3/day0）、planned_on、status（pending/sent/cancelled）、batch（可空）；唯一约束 `(service, target_expiry, kind)`。
- `MailBatch`：UUID、recipient、status（claimed/sent/failed/uncertain）、claimed_at、attempt_day、attempts_today、provider_message_id、error_code、created_at、sent_at；批次成员不可被另一个工作者同时发送。
- `ReminderRun`：started_at、finished_at、status、简要计数、error_code；`ReminderSettings`：单行 recipient。SMTP host、port、user、password、TLS 配置由服务器环境变量管理，设置页仅显示是否配置完整，不回显密码。
- 额外索引：Service.expires_on、Sale.sold_on、Reminder(status, planned_on)。金额数据库约束为非负整数；应用拒绝超过 999999999999 分的输入。额度用 DecimalField(max_digits=18, decimal_places=4)，不可空单位配合空额度。
- `TermUnit = Literal['day', 'week', 'month', 'year']`；`add_term(start: date, count: int, unit: TermUnit) -> date`。
- `parse_fen(text: str) -> int`、`format_yuan(fen: int) -> str`、`service_status(started_on: date, expires_on: date | None, ended: bool, today: date) -> str`。
- `SaleInput` 为 frozen dataclass：customer_id、product_id、sold_on、cost_fen、price_fen、submission_id，及可空 started_on、expires_on、term_count、term_unit、quota_amount、quota_unit，identifier/notes 默认空串。
- `purchase(data: SaleInput) -> Sale`；`renew(service_id: int, data: SaleInput, expected_revision: int) -> Sale`；`topup(service_id: int, data: SaleInput, expected_revision: int) -> Sale`。
- `correct_sale(sale_id: int, data: SaleInput, service_state: dict, expected_revision: int) -> Sale`：只改指定交易及明确提交的服务当前状态，不重算后续交易；保留原 submission_id，更新修改时间。
- `void_sale(sale_id: int, reason: str, service_state: dict, expected_revision: int) -> Sale`；`end_service(service_id: int, expected_revision: int) -> Service`；`month_totals(month: date) -> dict[str, int]` 返回 revenue_fen/cost_fen/profit_fen。
- `plan_due(now: datetime) -> int` 返回新建项目数；`send_due(now: datetime) -> dict[str, int]` 返回 sent/failed/uncertain/cancelled 项目数。两者独立调用且时间参数为带时区时间。
- `send_digest(batch: MailBatch) -> str` 返回 SMTP Message-ID；`run_cycle(now: datetime) -> dict[str, int]` 生成计划再发送并写运行记录。
- 统一业务错误为 `ValidationError`，冲突为自定义 `StaleServiceError`；HTTP 表单显示中文提示并保留输入。

## Task 1：可登录的应用骨架

**Files:** 创建 manage.py、pyproject.toml、requirements.lock、config/*、accounts/*、templates/base.html、templates/accounts/login.html、static/app.css、.env.example、.gitignore、tests/conftest.py、tests/test_auth.py。

**接口：** Django 路由 name `login/logout/dashboard`；保护采用 LoginRequiredMiddleware 加经营者权限检查，只有匿名登录入口和带独立密钥的任务入口例外。bootstrap_owner 拒绝创建第二个活跃经营者；登录和任务 HTTP 入口设置每 IP/每会话的短期速率限制，不用浏览器端限制代替服务器检查。

- [ ] 创建 Python 虚拟环境并锁定依赖；采用原生本地运行。若确认 SQLite，数据库存储在被 Git 忽略的本地数据目录；先验证运行时 SQLite 版本。启动命令记录到 README。
- [ ] 编写登录保护及 CSRF 用例：

```python
def test_anonymous_cannot_read_dashboard(client):
    response = client.get('/')
    assert response.status_code == 302
    assert '/login/' in response.url

def test_login_requires_csrf():
    from django.test import Client
    assert Client(enforce_csrf_checks=True).post('/login/', {}).status_code == 403
```

- [ ] 运行 `python -m pytest tests/test_auth.py -q`，记录首次失败（未创建路由或项目配置），再实现最小会话登录、POST 退出和受保护首页。关闭公开注册和不必要管理站点入口。
- [ ] 实现环境配置：开发明确 DEBUG、本机 ALLOWED_HOSTS；生产拒绝缺失 SECRET_KEY、数据库地址或不安全站点配置。时区固定、USE_TZ=True，生产 cookie 配置 Secure/HttpOnly/SameSite。
- [ ] 运行上述测试及 `python manage.py check`，确认通过；验证单经营者创建、错误密码提示、外部 next 地址不能重定向。
- [ ] 提交 `feat: add owner login and application shell`。

## Task 2：日期、金额和业务数据模型

**Files:** 创建 crm/models.py、catalog/models.py、billing/models.py、billing/inputs.py、billing/dates.py、billing/money.py、各模块 migrations、tests/test_dates_money.py；扩展tests/conftest.py。

**接口：** 实现固定契约的模型、SaleInput 和纯函数。fixture `customer`、`supplier`、`product` 提供有效实例；`sale_input` 是工厂 callable，默认成本 6000、售价 10000、日历日期 2026-10-16、月期限 1、新 UUID，每个参数可覆盖；`service_factory` 可覆盖 started_on/expires_on/created_at；`owner_client` 为已登录 Django client。

- [ ] 编写纯函数失败测试：

```python
from datetime import date
import pytest

@pytest.mark.parametrize('start,count,unit,end', [
    (date(2027,1,31),1,'month',date(2027,2,28)),
    (date(2028,2,29),1,'year',date(2029,2,28)),
    (date(2026,10,16),2,'week',date(2026,10,30)),
    (date(2026,10,16),7,'day',date(2026,10,23)),
])
def test_calendar_terms(start, count, unit, end):
    from billing.dates import add_term
    assert add_term(start, count, unit) == end

def test_money_exact_and_invalid_values():
    from billing.money import parse_fen
    assert parse_fen('0.29') == 29
    for value in ['-1', '1.001', 'NaN', 'Infinity', '1e100']:
        with pytest.raises(ValueError):
            parse_fen(value)
```

- [ ] 运行 `python -m pytest tests/test_dates_money.py -q`，确认失败；实现日历计算（calendar.monthrange）、Decimal 校验及整数分格式化，拒绝零或负期限、未知单位、到期早于开始日期。
- [ ] 按契约建立模型与数据库约束；以 `python manage.py makemigrations` 生成并审阅迁移。快照日期序列化为 ISO 字符串，金额为整数、额度为 Decimal 字符串。
- [ ] 为非负金额、额度单位成对输入、PROTECT 引用、唯一 submission_id 增加数据库用例并运行；再执行 `python manage.py migrate` 和 `python manage.py makemigrations --check --dry-run`。
- [ ] 提交 `feat: add service data model and calendar money rules`。

## Task 3：客户、上游与商品的日常管理

**Files:** 创建 crm/forms.py、views.py、urls.py，catalog/forms.py、views.py、urls.py，templates/crm/*、templates/catalog/*、tests/test_catalog_crm.py；修改 config/urls.py、static/app.css。

**接口：** 路由 name `customers/customer_detail/customer_create/customer_edit/suppliers/supplier_detail/supplier_create/supplier_edit/products/product_create/product_edit`；所有变更使用 POST+CSRF。查询参数 q 搜索，分页每页 25。

- [ ] 建立失败测试：

```python
import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_customer_multiple_contacts(owner_client):
    response = owner_client.post(reverse('customer_create'), {
        'name': '客户甲', 'notes': '', 'contacts-TOTAL_FORMS': '2',
        'contacts-INITIAL_FORMS': '0', 'contacts-0-kind': 'wechat',
        'contacts-0-value': 'wx-demo', 'contacts-1-kind': 'qq',
        'contacts-1-value': '123456',
    })
    from crm.models import Customer
    assert response.status_code == 302
    assert Customer.objects.get(name='客户甲').contacts.count() == 2
```

- [ ] 运行 `python -m pytest tests/test_catalog_crm.py -q` 确认失败；实现 ModelForm 与联系方式 inline formset，同一事务保存主表及联系方式。
- [ ] 商品支持自由输入平台/套餐/交付方式、标签、参考价、报价日期、期限、额度与质保备注；保留完整上游标题；停用后不能用于新购默认选择，但历史详情保留。
- [ ] 实现档案归档和删除规则：有业务引用只能归档；无引用草稿可在确认页删除；不以 GET 执行变更。测试商品报价更改不触碰已有 Sale.snapshot。
- [ ] 加用例：名称必填而联系方式可空；微信/QQ 搜索；notes 中 `<script>` 被转义；source_url 的 `javascript:` 被拒绝；匿名和无 CSRF 请求不能写入。
- [ ] 运行该文件与 auth 测试，确认通过；提交 `feat: manage customers suppliers and products`。

## Task 4：购买、续费、额度追加与历史纠错

**Files:** 创建 billing/services.py、forms.py、views.py、urls.py、templates/billing/sale_form.html、service_detail.html、sale_detail.html、sale_correct.html、sale_void.html、service_end.html、tests/test_billing.py；扩展 fixtures 和客户详情。

**接口：** 实现全部交易服务契约；路由 name `sale_create/service_detail/service_renew/service_topup/sale_detail/sale_correct/sale_void/service_end`。SQLite 使用短写事务，revision 条件更新用于检测过期表单；同一提交标识由唯一约束保障。客户 ID 必须与服务匹配；重复 submission_id 先返回已有同内容交易，不再延长，内容不一致则拒绝。

- [ ] 编写首条行为用例并运行至失败：

```python
import pytest

@pytest.mark.django_db
def test_duplicate_purchase_is_one_sale(sale_input):
    from billing.models import Sale
    from billing.services import purchase
    data = sale_input()
    first = purchase(data)
    second = purchase(data)
    assert first.pk == second.pk
    assert Sale.objects.count() == 1
    assert first.price_fen - first.cost_fen == 4000
```

- [ ] 实现 purchase 原子创建 Service 和 Sale，保存成交快照及前后状态，重复提交依赖数据库唯一约束兜底；用户输入保留准确整数分。
- [ ] 实现 renew：base=max(原到期日, sold_on)，没有原到期日时取 sold_on；允许显式 expires_on 覆盖。更新当前商品、到期日、revision，新增交易。topup 累加购买额度且单位必须相同；明确填写有效期才修改到期日期。
- [ ] 编写并通过用例：同客户两个相同套餐不合并；分别续费；月末/逾期续费；换上游后旧交易来源不变；负利润可保存；旧 revision 抛 StaleServiceError；重复续费只延长一次；不活跃商品拒绝新购。
- [ ] 实现 correct_sale 和 void_sale：表单展示交易快照及当前服务状态，要求显式确认服务到期日/结束状态/累计购买量；旧金额和前后状态存入 snapshot 中的 correction_history，包含修改时间。作废原因必填；不自动改写其他成交记录。end_service 幂等结束服务。
- [ ] 浏览器表单带提交 UUID 和 revision；测试外部客户 ID 与服务混配、重复 POST、作废已非最新交易、事务异常回滚不留下孤立交易。
- [ ] 运行 `python -m pytest tests/test_billing.py tests/test_dates_money.py -q`，确认通过；提交 `feat: record purchases renewals and immutable sale history`。

## Task 5：首页、筛选和人民币利润统计

**Files:** 创建 billing/queries.py、templates/billing/dashboard.html、sales.html、services.html、tests/test_dashboard.py；修改 billing/views.py、urls.py、templates/crm/customer_detail.html。

**接口：** month_totals 契约；路由 name `dashboard/sales/services`；过滤参数 customer/supplier/product/sold_from/sold_to/expiry_from/expiry_to/status。状态值 upcoming/active/today/overdue/ended/no_expiry 对应中文标签。

- [ ] 先写汇总测试并运行至失败：

```python
import pytest
from datetime import date

@pytest.mark.django_db
def test_profit_is_actual_yuan_difference(sale_input):
    from billing.services import purchase
    from billing.queries import month_totals
    purchase(sale_input(cost_fen=6000, price_fen=10000))
    purchase(sale_input(cost_fen=5000, price_fen=4000))
    assert month_totals(date(2026,10,1)) == {
        'revenue_fen': 14000, 'cost_fen': 11000, 'profit_fen': 3000,
    }
```

- [ ] 用数据库聚合计算月度非作废交易；月份使用 sold_on 的闭开区间；空月份返回全零。实现筛选、分页和带联系信息的待办列表。
- [ ] 测试作废排除、服务提前结束仍保留有效成交统计、报价改变无影响、跨年月份、未来开始不误标逾期、无到期不进入到期清单。
- [ ] 首页面板显示本月销售、成本、差价利润及将到期/今天到期/逾期清单；客户详情聚合多服务及购买历史。
- [ ] 运行 `python -m pytest tests/test_dashboard.py -q` 通过；提交 `feat: show expiry worklist and sales profit dashboard`。

## Task 6：提醒生成、恢复与失效取消

**Files:** 创建 reminders/models.py、planner.py、management/commands/run_reminders.py、migrations/*、tests/test_reminder_planner.py；修改 billing/services.py。

**接口：** plan_due、run_cycle；此任务 run_cycle 先只生成计划，任务 7 接入 send_due。billing 的到期变更或结束事务取消匹配旧状态的 pending 提醒。

- [ ] 使用冻结时间参数的测试，不依赖机器日期：

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo
import pytest

@pytest.mark.django_db
def test_before3_is_generated_once(service_factory):
    from reminders.planner import plan_due
    from reminders.models import Reminder
    service_factory(expires_on=date(2026,10,19),
                    created_at=datetime(2026,10,1,tzinfo=ZoneInfo('Asia/Hong_Kong')))
    now = datetime(2026,10,16,9,tzinfo=ZoneInfo('Asia/Hong_Kong'))
    assert plan_due(now) == 1
    assert plan_due(now) == 0
    assert Reminder.objects.filter(kind='before3').count() == 1
```

- [ ] 运行 `python -m pytest tests/test_reminder_planner.py -q` 至失败；实现对有效 Service 计算两个节点，planned_on 不早于服务创建本地日期，且节点已经到达才创建。当前日 09:00 前不生成当天节点，往日漏项可恢复。
- [ ] 使用唯一约束及冲突处理保障重复扫描；只补发当前 target_expiry 匹配且未结束的项目。发送历史不删除；变更期限取消旧 pending，保留旧 sent。
- [ ] 测试当天到期、跨月提前 3 天、停机 4 天后恢复、历史逾期补录、无期限、服务结束、续费后旧提醒取消、新日期计划生成、同日 09:00 后补录可加入汇总。
- [ ] 对实际选用数据库使用磁盘测试库和独立连接进行并发生成验证，断言一个节点只有一条；SQLite 对短写冲突设置有界重试，不使用 select_for_update 模拟行锁。执行迁移一致性检查。
- [ ] 提交 `feat: plan expiry reminders with recovery and deduplication`。

## Task 7：邮件发送、设置、日志和受保护调度

**Files:** 创建 reminders/mail.py、sender.py、forms.py、views.py、urls.py、templates/reminders/settings.html、runs.html、templates/reminders/email_digest.txt、email_digest.html、tests/test_reminder_sender.py、ops/systemd/ai-subscriptions-reminders.service、ai-subscriptions-reminders.timer；修改 run_reminders.py、config/urls.py、.env.example。

**接口：** send_digest、send_due、run_cycle；路由 name `reminder_settings/reminder_runs/reminder_test/reminder_retry/reminder_job`。任务接口 `/internal/reminders/run/` 为 POST，仅以 Authorization Bearer 常量时间比较校验独立任务密钥，禁止 query 参数密钥；CSRF 仅对此入口豁免，其他设置表单仍保护。

- [ ] 写失败用例，补充 fixture `due_batch`（当天两个有效提醒及接收邮箱）：

```python
import pytest
from django.core import mail

@pytest.mark.django_db
def test_digest_excludes_procurement_cost(due_batch, settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    from reminders.mail import send_digest
    message_id = send_digest(due_batch)
    assert message_id
    assert len(mail.outbox) == 1
    assert '采购成本' not in mail.outbox[0].body
    assert '差价利润' not in mail.outbox[0].body
```

- [ ] 运行至失败；SMTP 适配设置连接超时 10 秒，生产要求 TLS/SSL；纯文本和 HTML 双版本渲染、包含客户联系及后台详情链接。捕获连接/认证/超时异常，只保存脱敏错误代码。
- [ ] 生成待发批次，通过状态条件更新及唯一约束原子认领，记录租约及批次成员，短事务提交后再准备发送；SQLite 不支持依赖行锁的认领。
- [ ] 发送前短事务重新核对服务期限及版本，去除失效项目，提交后调用 SMTP；网络调用期间不持有数据库写锁。重检之后发生的续费可能与已经开始的投递重叠，此时不能撤回邮件；日志保存发送快照，邮件标明统计时间。
- [ ] 同批次使用固定 Message-ID；成功才更新 Reminder.sent。每日至多首次加 3 次重试，间隔至少 15 分钟；跨日重置尝试次数，保留计划日期。进程中断或 10 秒超时结果不明标 uncertain，过期认领在 5 分钟后进入恢复流程；不能把 Message-ID 当成 SMTP 端到端幂等保证。
- [ ] 测试连接拒绝为 failed、投递后超时为 uncertain、失败不标 sent、次日补发、并发发送不重复认领、发送前续费排除、旧 claimed 恢复、邮箱变更用新批次、测试邮件不影响业务提醒。邮箱变更与发送批次各自保留收件人快照。
- [ ] 设置页仅保存接收邮箱，邮件连接参数通过部署环境配置；显示缺失项名称和配置状态，不显示凭据。提供测试邮件、发送日志、手动重试和最近扫描时间；无邮箱时显示未配置并保留 pending。
- [ ] systemd timer 每 15 分钟触发一次 `python manage.py run_reminders`，09:00 及补发判断由应用负责；使用独立 oneshot service 及禁止重入的任务认领，不依赖浏览器或 CI/CD 定时调度业务提醒。
- [ ] 运行 `python -m pytest tests/test_reminder_planner.py tests/test_reminder_sender.py tests/test_auth.py -q` 及实际数据库并发用例；提交 `feat: send logged expiry digests and secure scheduled runs`。

## Task 8：自适应界面、完整验收和部署交付

**Files:** 修改 templates/*、static/app.css、app.js；创建 tests/e2e/test_owner_flow.py、.github/workflows/ci.yml、deploy.yml、ops/deploy.sh、ops/systemd/*、ops/nginx.conf、ops/backup.py、restore.py、docs/deployment.md、README.md。

**接口：** 保留前述 URL 名称和表单提交契约；浏览器测试使用独立数据库和内存邮件，不发送真实客户邮件。

- [ ] 先编写浏览器流程断言：

```python
def test_owner_can_open_customer_on_mobile(page, live_server, owner_client, customer):
    # session cookie 来自 owner_client，使用 Django 测试配置的非 Secure 本地 cookie。
    page.context.add_cookies([{
        'name': 'sessionid', 'value': owner_client.cookies['sessionid'].value,
        'url': live_server.url,
    }])
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto(f'{live_server.url}/customers/{customer.pk}/')
    page.get_by_role('heading', name=customer.name, exact=True).wait_for()
    assert page.locator('html').evaluate('(el) => el.scrollWidth <= innerWidth')
```

- [ ] 运行 `python -m pytest tests/e2e -q`，确认必要行为先失败；完成自定义中文界面：浅色背景、清晰表格、金额右对齐、状态文字与颜色并用、左侧桌面导航及手机折叠菜单。390px 使用卡片或表格内部滚动，页面本身不横向溢出。
- [ ] 表单展示成本、售价、差价与日期预览；后端重新验证，不信任 JavaScript 计算；输入有 label，错误可定位，保存后有反馈，空列表提供新增入口；作废、结束、归档使用确认页。
- [ ] 浏览器走通建渠道→建商品→建客户及两种联系方式→购买两项服务→续费其中一项→检查利润和历史→生成提醒→查看日志。测试恶意备注转义、无 CSRF 修改失败及退出后接口拒绝。
- [ ] 按部署修订生成 GitHub Actions、SSH 发布脚本、systemd 应用服务和提醒 timer、Nginx 配置；上传不可变提交产物到 releases/<sha>，独立共享数据和环境配置；迁移前停写和一致性备份，再迁移、切换版本并健康检查。
- [ ] 若采用 SQLite，以 Python sqlite3.Connection.backup() 创建一致性快照，验证 integrity_check，并在临时路径恢复比较客户/交易/提醒计数。恢复脚本不默认覆盖生产；发布过程不复制开发库或覆盖线上数据库。
- [ ] README 覆盖 Windows 本地运行、初始化经营者、演示数据开关、测试、邮件配置、09:00/15 分钟调度、SMTP 不确定投递说明、备份恢复。部署说明区分“本地验证通过”与“已在线运行”。
- [ ] 执行完整检查：

```powershell
python -m pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
# 为生产检查注入专用测试环境配置，不能复用或打印真实凭据。
python manage.py check --deploy
# 实际浏览器验收另存屏幕截图至本地验收产物目录。
git diff --check
```

- [ ] 所有失败均修复或具体报告，真实 SMTP/在线任务只有获得可用配置后才能标记实投递通过；缺少凭据时保留完整应用、设置状态和邮件测试证据，不编造已上线。
- [ ] 提交 `feat: finish responsive owner workflow and deployment guide`，输出文件、启动方式、验收结果及剩余部署配置。

## 需求覆盖与计划自审

| 设计范围 | 落地任务 |
| --- | --- |
| 个人登录与网页访问 | 1、8 |
| 客户多联系方式及多服务 | 2、3、4、8 |
| 手动上游及自定义商品、质保备注 | 2、3 |
| 日周月年、月末、手动到期 | 2、4 |
| 成交快照、采购销售、负利润、续费历史 | 2、4、5 |
| 无有效期额度及累计购买量 | 2、4、6 |
| 筛选、首页待办及月度汇总 | 3、5 |
| 编辑、作废、结束、归档 | 3、4 |
| 两个提醒节点、汇总邮件、补发与取消 | 6、7 |
| 幂等、失败重试、不确定投递、运行日志 | 4、6、7 |
| 中文自适应、安全、备份恢复 | 1、3、7、8 |
| 设计文档的 14 项验收场景 | 2 至 8 的单元、集成和浏览器用例 |

自审结果：明确了金额/日期/接口名称，覆盖设计所有页面与业务规则；没有将剩余额度、自动交付或支付引入第一版。SMTP 配置采用服务器环境变量以符合设计的凭据规则，网页负责接收邮箱和配置状态。任务 4 对交易纠错和作废都要求明确确认当前服务状态，避免回滚后续续费。

## 执行交接

建议由主助手在当前会话按任务顺序实施，因为数据模型、交易规则和提醒状态关系紧密，连续上下文便于保持一致。计划确认后读取 executing-plans 与 using-git-worktrees 技能；如用户选择子代理实施，再按其授权使用 subagent-driven-development。当前阶段不开始产品实现。
