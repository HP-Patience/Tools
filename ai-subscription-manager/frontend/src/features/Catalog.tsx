import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Plus, ArrowUpRight, Pencil, Archive, Trash2 } from "lucide-react";
import { all, request, mutate } from "../api/client";
import type { Customer, Supplier, Product, Page } from "../api/types";
import {
  money,
  yuan,
  Field,
  FormSection,
  Dialog,
  ErrorNotice,
  Empty,
  SearchBox,
  Pager,
} from "../components/ui";
import { PageGuide } from "../components/Guide";
type Resource = "customers" | "suppliers" | "products";
type Row = Customer | Supplier | Product;
const names = { customers: "客户", suppliers: "上游渠道", products: "商品" };
export function Catalog({ kind }: { kind: Resource }) {
  const [params, setParams] = useSearchParams();
  const adding = params.get("new") === "1";
  const closeEditor = () => {
    setEditing(undefined);
    if (adding) {
      const next = new URLSearchParams(params);
      next.delete("new");
      setParams(next, { replace: true });
    }
  };
  const [search, setSearch] = useState(""),
    [page, setPage] = useState(1),
    [editing, setEditing] = useState<Row | null | undefined>(undefined),
    [error, setError] = useState<unknown>(null),
    [action, setAction] = useState<{ row: Row; remove: boolean } | null>(null);
  const cache = useQueryClient();
  const query = useQuery({
    queryKey: [kind, search, page],
    queryFn: () =>
      request<Page<Row>>(
        `/${kind}/?q=${encodeURIComponent(search)}&page=${page}`,
      ),
  });
  async function confirmAction() {
    if (!action) return;
    try {
      if (action.remove)
        await request(`/${kind}/${action.row.id}/`, { method: "DELETE" });
      else
        await mutate(
          `/${kind}/${action.row.id}/`,
          kind === "customers"
            ? { archived: !(action.row as Customer).archived_at }
            : { is_active: !(action.row as Supplier).is_active },
          "PATCH",
        );
      await cache.invalidateQueries();
      setAction(null);
    } catch (e) {
      setError(e);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {kind === "customers"
              ? "RELATIONSHIPS"
              : kind === "suppliers"
                ? "SUPPLY NETWORK"
                : "PRODUCT CATALOG"}
          </span>
          <h1>{names[kind]}管理</h1>
          <p>
            {kind === "customers"
              ? "每一位客户，每一次长期合作。"
              : kind === "suppliers"
                ? "把可靠的供货来源，留在自己的渠道库。"
                : "统一管理套餐、交付方式与参考报价。"}
          </p>
        </div>
        <button className="primary" onClick={() => setEditing(null)}>
          <Plus size={17} />
          添加{names[kind]}
        </button>
      </div>
      <PageGuide area={kind} />
      <ErrorNotice error={query.error || error} />
      <section className="panel">
        <div className="panel-toolbar">
          <SearchBox
            value={search}
            onChange={(v) => {
              setSearch(v);
              setPage(1);
            }}
          />
          <span className="muted">
            {query.data?.count || 0} 个{names[kind]}
          </span>
        </div>
        {query.isPending ? (
          <div className="loading">正在读取记录…</div>
        ) : !query.data?.results.length ? (
          <Empty message={`还没有${names[kind]}记录`} />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{names[kind]}名称</th>
                  {kind === "customers" ? (
                    <>
                      <th>联系方式</th>
                      <th>备注</th>
                    </>
                  ) : kind === "suppliers" ? (
                    <>
                      <th>网址 / 联系人</th>
                      <th>联系方式</th>
                    </>
                  ) : (
                    <>
                      <th>平台 / 交付方式</th>
                      <th>上游渠道</th>
                      <th className="numeric">成本 / 售价</th>
                    </>
                  )}
                  <th>状态</th>
                  <th className="align-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {query.data.results.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <div className="identity">
                        <span
                          className={
                            "avatar " +
                            (kind === "products" ? "product-avatar" : "")
                          }
                        >
                          {row.name.slice(0, 1)}
                        </span>
                        <div>
                          {kind === "customers" ? (
                            <Link
                              className="strong"
                              to={"/customers/" + row.id}
                            >
                              {row.name}
                            </Link>
                          ) : (
                            <strong>{row.name}</strong>
                          )}
                          {kind === "products" && (
                            <small>{(row as Product).plan}</small>
                          )}
                        </div>
                      </div>
                    </td>
                    {kind === "customers" ? (
                      <>
                        <td>
                          {(row as Customer).contacts.map((c, i) => (
                            <div className="contact" key={i}>
                              <span>
                                {c.kind === "wechat"
                                  ? "微信"
                                  : c.kind === "phone"
                                    ? "电话"
                                    : c.kind === "email"
                                      ? "邮箱"
                                      : c.kind}
                              </span>
                              {c.value}
                            </div>
                          ))}
                        </td>
                        <td className="notes-cell">
                          {(row as Customer).notes || "—"}
                        </td>
                      </>
                    ) : kind === "suppliers" ? (
                      <>
                        <td>
                          {(row as Supplier).url ? (
                            <a
                              href={(row as Supplier).url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              访问渠道 <ArrowUpRight size={13} />
                            </a>
                          ) : (
                            "—"
                          )}
                          <small>{(row as Supplier).contact_name}</small>
                        </td>
                        <td>{(row as Supplier).contact_details || "—"}</td>
                      </>
                    ) : (
                      <>
                        <td>
                          {(row as Product).platform || "—"}
                          <small>{(row as Product).delivery}</small>
                        </td>
                        <td>{(row as Product).supplier_name}</td>
                        <td className="numeric">
                          <small>{money((row as Product).cost_fen)}</small>
                          <strong>{money((row as Product).price_fen)}</strong>
                        </td>
                      </>
                    )}
                    <td>
                      <span
                        className={
                          "badge " +
                          ((
                            kind === "customers"
                              ? !(row as Customer).archived_at
                              : (row as Supplier).is_active
                          )
                            ? "active"
                            : "ended")
                        }
                      >
                        {(
                          kind === "customers"
                            ? !(row as Customer).archived_at
                            : (row as Supplier).is_active
                        )
                          ? "启用"
                          : "已归档 / 停用"}
                      </span>
                    </td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="text-button"
                          aria-label={"编辑" + row.name}
                          onClick={() => setEditing(row)}
                        >
                          <Pencil size={15} /> 编辑
                        </button>
                        <button
                          className="text-button"
                          aria-label={"切换状态" + row.name}
                          onClick={() => setAction({ row, remove: false })}
                        >
                          <Archive size={15} />
                          {kind === "customers"
                            ? (row as Customer).archived_at
                              ? "恢复"
                              : "归档"
                            : (row as Supplier).is_active
                              ? "停用"
                              : "启用"}
                        </button>
                        <button
                          className="text-button danger-text"
                          aria-label={"删除" + row.name}
                          onClick={() => setAction({ row, remove: true })}
                        >
                          <Trash2 size={15} /> 删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager page={page} total={query.data?.count || 0} onChange={setPage} />
      </section>
      {(editing !== undefined || adding) && (
        <ResourceForm
          kind={kind}
          initial={editing ?? null}
          onClose={closeEditor}
        />
      )}
      {action && (
        <Dialog
          title={action.remove ? "确认删除记录" : "确认切换状态"}
          onClose={() => setAction(null)}
        >
          <p>
            即将处理「{action.row.name}
            」。已有交易关联的记录只能归档或停用，历史交易会保留。
          </p>
          <ErrorNotice error={error} />
          <footer className="form-footer">
            <button className="secondary" onClick={() => setAction(null)}>
              取消
            </button>
            <button className="primary" onClick={confirmAction}>
              确认
            </button>
          </footer>
        </Dialog>
      )}
    </>
  );
}
function ResourceForm({
  kind,
  initial,
  onClose,
}: {
  kind: Resource;
  initial: Row | null;
  onClose: () => void;
}) {
  const cache = useQueryClient(),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const p = initial as Product | null,
    c = initial as Customer | null,
    s = initial as Supplier | null;
  const [values, setValues] = useState<Record<string, string>>(() => ({
    name: initial?.name || "",
    notes: (initial as Customer)?.notes || "",
    other_kind: "",
    other_value: "",
    wechat: c?.contacts?.find((x) => x.kind === "wechat")?.value || "",
    qq: c?.contacts?.find((x) => x.kind === "qq")?.value || "",
    phone: c?.contacts?.find((x) => x.kind === "phone")?.value || "",
    email: c?.contacts?.find((x) => x.kind === "email")?.value || "",
    url: s?.url || "",
    contact_name: s?.contact_name || "",
    contact_details: s?.contact_details || "",
    supplier_id: String(p?.supplier_id || ""),
    platform: p?.platform || "",
    plan: p?.plan || "",
    delivery: p?.delivery || "",
    source_name: p?.source_name || "",
    source_url: p?.source_url || "",
    cost: String((p?.cost_fen || 0) / 100),
    price: String((p?.price_fen || 0) / 100),
    quoted_on: p?.quoted_on || "",
    term_count: p?.term_count ? String(p.term_count) : "",
    term_unit: p?.term_unit || "month",
    quota_amount: p?.quota_amount || "",
    quota_unit: p?.quota_unit || "",
    warranty_notes: p?.warranty_notes || "",
    tags: p?.tags?.join("，") || "",
  }));
  const suppliers = useQuery({
    queryKey: ["supplier-options"],
    queryFn: () => all<Supplier>("/suppliers/"),
    enabled: kind === "products",
  });
  const set = (key: string, v: string) =>
    setValues((old) => ({ ...old, [key]: v }));
  const field = (
    key: string,
    label: string,
    type = "text",
    required = false,
    hint?: string,
    placeholder?: string,
  ) => (
    <Field key={key} label={label} hint={hint}>
      <input
        type={type}
        placeholder={placeholder}
        min={type === "number" ? 1 : undefined}
        step={type === "number" ? 1 : undefined}
        inputMode={key === "cost" || key === "price" ? "decimal" : undefined}
        required={required}
        value={values[key]}
        onChange={(e) => set(key, e.target.value)}
      />
    </Field>
  );
  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      let data: Record<string, unknown> = { name: values.name };
      if (kind === "customers")
        data = {
          ...data,
          notes: values.notes,
          contacts: [
            ...(c?.contacts?.filter(
              (x) => !["wechat", "qq", "phone", "email"].includes(x.kind),
            ) || []),
            ...(values.other_kind && values.other_value
              ? [{ kind: values.other_kind, value: values.other_value }]
              : []),
            ...["wechat", "qq", "phone", "email"]
              .filter((k) => values[k])
              .map((k) => ({ kind: k, value: values[k] })),
          ],
        };
      else if (kind === "suppliers")
        data = {
          ...data,
          url: values.url,
          contact_name: values.contact_name,
          contact_details: values.contact_details,
          notes: values.notes,
        };
      else
        data = {
          ...data,
          supplier_id: Number(values.supplier_id),
          platform: values.platform,
          plan: values.plan,
          delivery: values.delivery,
          source_name: values.source_name,
          source_url: values.source_url,
          cost_fen: yuan(values.cost),
          price_fen: yuan(values.price),
          quoted_on: values.quoted_on || null,
          term_count: values.term_count ? Number(values.term_count) : null,
          term_unit: values.term_count ? values.term_unit : null,
          quota_amount: values.quota_amount || null,
          quota_unit: values.quota_unit || null,
          warranty_notes: values.warranty_notes,
          tags: values.tags
            .split(/[,，]/)
            .map((s) => s.trim())
            .filter(Boolean),
        };
      await mutate(
        `/${kind}/${initial ? initial.id + "/" : ""}`,
        data,
        initial ? "PATCH" : "POST",
      );
      await cache.invalidateQueries();
      onClose();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={(initial ? "编辑" : "添加") + names[kind]}
      onClose={onClose}
      wide
    >
      <form onSubmit={save} className="structured-form">
        <div className="form-body">
          <p className="form-intro">
            {kind === "products"
              ? "先确认商品和供货渠道，再补充价格与订阅规则。"
              : kind === "customers"
                ? "先记录客户称呼，再留下方便联系的方式。"
                : "先保存渠道名称，其余资料可以随时补充。"}
            <span>带「必填」的项目需要填写，其余可稍后完善。</span>
          </p>
          <ErrorNotice error={error || suppliers.error} />
          <FormSection
            title={
              kind === "products"
                ? "商品信息"
                : kind === "customers"
                  ? "客户信息"
                  : "渠道信息"
            }
            step="01"
            description={
              kind === "products"
                ? "商品名称与上游渠道是这条记录的核心。"
                : "填写便于查找和识别的名称。"
            }
          >
            {field(
              "name",
              names[kind] + "名称",
              "text",
              true,
              undefined,
              kind === "products"
                ? "例如 ChatGPT Plus · 月卡代充"
                : kind === "customers"
                  ? "客户姓名或常用昵称"
                  : "商家或店铺名称",
            )}
            {kind === "products" && (
              <>
                <Field
                  label="上游渠道"
                  hint={
                    suppliers.isPending
                      ? "正在读取渠道…"
                      : !suppliers.data?.length
                        ? "请先在上游渠道中添加供货商。"
                        : undefined
                  }
                >
                  <select
                    required
                    value={values.supplier_id}
                    onChange={(e) => set("supplier_id", e.target.value)}
                  >
                    <option value="">请选择渠道</option>
                    {suppliers.data
                      ?.filter((v) => v.is_active || v.id === p?.supplier_id)
                      .map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.name}
                        </option>
                      ))}
                  </select>
                </Field>
              </>
            )}
            {kind === "suppliers" &&
              field("url", "渠道网址", "url", false, undefined, "https://")}
          </FormSection>
          {kind === "products" ? (
            <>
              <FormSection
                title="参考报价"
                step="02"
                description="全部以人民币记录；实际成交时仍可单独调整。"
              >
                {field(
                  "cost",
                  "参考采购价（元）",
                  "text",
                  true,
                  "建议包含支付手续费，按最终采购总额记录。",
                )}
                {field(
                  "price",
                  "参考售价（元）",
                  "text",
                  true,
                  "尚未定价可暂记 0，销售前请确认。",
                )}
                <div className="pricing-preview" aria-live="polite">
                  <span>参考差价</span>
                  <strong>
                    {(() => {
                      try {
                        return money(yuan(values.price) - yuan(values.cost));
                      } catch {
                        return "—";
                      }
                    })()}
                  </strong>
                  <small>售价 − 采购成本，不含其他经营费用</small>
                </div>
                {field(
                  "quoted_on",
                  "报价记录日期",
                  "date",
                  false,
                  "方便判断这份报价是否仍然有效。",
                )}
              </FormSection>
              <FormSection
                title="订阅期限"
                step="03"
                description="按天、周、月或年设置；没有固定期限可留空。"
              >
                {field(
                  "term_count",
                  "默认期限数量",
                  "number",
                  false,
                  "例如 1 个月或 30 天；留空则不预设到期日。",
                  "填写正整数",
                )}
                <Field label="期限单位">
                  <select
                    value={values.term_unit}
                    onChange={(e) => set("term_unit", e.target.value)}
                  >
                    <option value="day">天</option>
                    <option value="week">周</option>
                    <option value="month">月</option>
                    <option value="year">年</option>
                  </select>
                </Field>
              </FormSection>
              <FormSection
                title="质保与售后"
                description="把赔付范围、退款规则和充值限制写清楚。"
              >
                <Field label="质保条件" wide>
                  <textarea
                    rows={4}
                    placeholder="例如保掉订阅 30 天，封号不保；提前续费会覆盖剩余时长。"
                    value={values.warranty_notes}
                    onChange={(e) => set("warranty_notes", e.target.value)}
                  />
                </Field>
              </FormSection>
              <FormSection
                title="更多商品资料"
                description="选填 · 平台、套餐、交付方式、来源、标签与额度"
                collapsible
              >
                {field(
                  "platform",
                  "平台，如 OpenAI",
                  "text",
                  false,
                  undefined,
                  "例如 ChatGPT、Claude",
                )}
                {field(
                  "plan",
                  "套餐，如 Plus",
                  "text",
                  false,
                  undefined,
                  "例如 Plus、Pro 5x",
                )}
                {field(
                  "delivery",
                  "交付方式，如代充",
                  "text",
                  false,
                  undefined,
                  "例如账号代充、卡密、独享号",
                )}
                {field("source_name", "上游原始商品名")}
                {field(
                  "source_url",
                  "商品链接",
                  "url",
                  false,
                  undefined,
                  "https://",
                )}
                {field(
                  "tags",
                  "标签（逗号分隔）",
                  "text",
                  false,
                  undefined,
                  "例如待验证、iOS渠道",
                )}
                {field(
                  "quota_amount",
                  "额度（可选）",
                  "text",
                  false,
                  "填写额度时，请同时填写额度单位。",
                )}
                {field(
                  "quota_unit",
                  "额度单位，如百万Token",
                  "text",
                  false,
                  "与额度成对填写。",
                  "例如百万 Token",
                )}
              </FormSection>
            </>
          ) : (
            <>
              <FormSection
                title="联系方式"
                step="02"
                description={
                  kind === "customers"
                    ? "按实际情况填写，无需把每一种联系方式都填满。"
                    : "保存日常沟通与售后使用的联系人。"
                }
              >
                {kind === "customers" ? (
                  <>
                    {field(
                      "wechat",
                      "微信号",
                      "text",
                      false,
                      undefined,
                      "客户常用微信号",
                    )}
                    {field("qq", "QQ号")}
                    {field("phone", "联系电话", "tel")}
                    {field("email", "联系邮箱", "email")}
                  </>
                ) : (
                  <>
                    {field("contact_name", "联系人")}
                    <Field
                      label="联系方式"
                      hint="可同时记录微信、QQ、电话和邮箱。"
                    >
                      <textarea
                        rows={3}
                        value={values.contact_details}
                        onChange={(e) => set("contact_details", e.target.value)}
                        placeholder="例如微信：xxx；QQ群：xxx"
                      />
                    </Field>
                  </>
                )}
              </FormSection>
              {kind === "customers" && (
                <FormSection
                  title="其他联系方式"
                  description="选填 · 有其他联系渠道时再展开"
                  collapsible
                >
                  {field(
                    "other_kind",
                    "其他联系方式类型（可选）",
                    "text",
                    false,
                    "类型与账号需要一起填写。",
                    "例如 Telegram",
                  )}
                  {field("other_value", "其他联系方式账号（可选）")}
                </FormSection>
              )}
              <FormSection
                title="补充备注"
                description="记录合作情况、偏好或需要特别留意的事项。"
              >
                <Field label="备注" wide>
                  <textarea
                    rows={4}
                    placeholder={
                      kind === "customers"
                        ? "例如客户偏好的套餐、联系时间等"
                        : "例如代理条件、售后规则、试单情况等"
                    }
                    value={values.notes}
                    onChange={(e) => set("notes", e.target.value)}
                  />
                </Field>
              </FormSection>
            </>
          )}
        </div>
        <footer className="form-footer">
          <span className="form-footer-note">
            {initial ? "保存后更新这条记录" : "保存后可继续补充资料"}
          </span>
          <button type="button" className="secondary" onClick={onClose}>
            取消
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "正在保存…" : "保存记录"}
          </button>
        </footer>
      </form>
    </Dialog>
  );
}
