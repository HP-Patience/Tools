import { newSubmissionId } from "../api/id";
import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  Plus,
  ArrowUpRight,
  RefreshCw,
  ArrowLeft,
  ArrowRight,
  CircleHelp,
} from "lucide-react";
import { all, request, mutate } from "../api/client";
import type {
  Customer,
  Supplier,
  Product,
  Service,
  Sale,
  Page,
} from "../api/types";
import { PageGuide } from "../components/Guide";
import { previewExpiry } from "../components/calendar";
import {
  money,
  yuan,
  localDay,
  Field,
  FormSection,
  Dialog,
  ErrorNotice,
  Empty,
  SearchBox,
  Pager,
  Badge,
} from "../components/ui";
export function ServiceTable({ rows }: { rows: Service[] }) {
  return !rows.length ? (
    <Empty message="还没有订阅服务" />
  ) : (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>客户 / 服务</th>
            <th>服务标识</th>
            <th>到期日期</th>
            <th>状态</th>
            <th>供货渠道</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td>
                <Link className="strong" to={"/customers/" + s.customer_id}>
                  {s.customer_name}
                </Link>
                <small>{s.product_name}</small>
              </td>
              <td>
                {s.identifier || "—"}
                {s.quota_unit && (
                  <small>
                    累计购买 {s.purchased_quota} {s.quota_unit}
                  </small>
                )}
              </td>
              <td className="date-cell">{s.expires_on || "无固定期限"}</td>
              <td>
                <Badge status={s.status} />
              </td>
              <td>{s.supplier_name}</td>
              <td>
                <Link className="text-button" to={"/services/" + s.id}>
                  查看 <ArrowUpRight size={14} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function SaleTable({
  rows,
  onSelect,
}: {
  rows: Sale[];
  onSelect?: (s: Sale) => void;
}) {
  return !rows.length ? (
    <Empty message="还没有成交记录" />
  ) : (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>成交日期 / 客户</th>
            <th>服务 / 类型</th>
            <th className="numeric">采购成本</th>
            <th className="numeric">销售金额</th>
            <th className="numeric">差价利润</th>
            <th>状态</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td>
                {s.sold_on}
                <small>{s.snapshot.customer_name}</small>
              </td>
              <td>
                {s.snapshot.product_name}
                <small>
                  {{ purchase: "新购", renewal: "续费", topup: "追加额度" }[
                    s.kind
                  ] || s.kind}{" "}
                  · {s.snapshot.supplier_name}
                </small>
              </td>
              <td className="numeric">{money(s.cost_fen)}</td>
              <td className="numeric">{money(s.price_fen)}</td>
              <td
                className={
                  "numeric " +
                  (s.price_fen < s.cost_fen ? "danger-text" : "profit")
                }
              >
                {money(s.price_fen - s.cost_fen)}
              </td>
              <td>
                <span className={"badge " + (s.voided_at ? "ended" : "active")}>
                  {s.voided_at ? "已作废" : "已成交"}
                </span>
              </td>
              <td>
                {onSelect ? (
                  <button className="text-button" onClick={() => onSelect(s)}>
                    详情
                  </button>
                ) : (
                  <Link
                    className="text-button"
                    to={"/services/" + s.service_id}
                  >
                    服务 <ArrowUpRight size={14} />
                  </Link>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Records({ kind }: { kind: "services" | "sales" }) {
  const [routeParams, setRouteParams] = useSearchParams();
  const adding = routeParams.get("new") === "1";
  const closePurchase = () => {
    setShow(false);
    if (adding) {
      const next = new URLSearchParams(routeParams);
      next.delete("new");
      setRouteParams(next, { replace: true });
    }
  };
  const [page, setPage] = useState(1),
    [q, setQ] = useState(""),
    [status, setStatus] = useState(""),
    [customer, setCustomer] = useState(""),
    [supplier, setSupplier] = useState(""),
    [product, setProduct] = useState(""),
    [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [show, setShow] = useState(false),
    [selected, setSelected] = useState<Sale | null>(null);
  const customers = useQuery({
    queryKey: ["customer-options"],
    queryFn: () => all<Customer>("/customers/"),
  });
  const suppliers = useQuery({
    queryKey: ["supplier-options"],
    queryFn: () => all<Supplier>("/suppliers/"),
  });
  const products = useQuery({
    queryKey: ["product-options"],
    queryFn: () => all<Product>("/products/"),
  });
  const params = new URLSearchParams({
    page: String(page),
    q,
    ...(status ? { status } : {}),
    ...(customer ? { customer_id: customer } : {}),
    ...(supplier ? { supplier_id: supplier } : {}),
    ...(product ? { product_id: product } : {}),
    ...(from ? { [kind === "sales" ? "sold_from" : "expiry_from"]: from } : {}),
    ...(to ? { [kind === "sales" ? "sold_to" : "expiry_to"]: to } : {}),
  });
  const query = useQuery({
    queryKey: [kind, page, q, status, customer, supplier, product, from, to],
    queryFn: () => request<Page<Service> | Page<Sale>>(`/${kind}/?${params}`),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {kind === "services" ? "SERVICE PORTFOLIO" : "TRANSACTION LEDGER"}
          </span>
          <h1>{kind === "services" ? "订阅与服务" : "交易记录"}</h1>
          <p>
            {kind === "services"
              ? "一项服务，一个独立的期限。"
              : "保存每一笔成交，让成本和利润清清楚楚。"}
          </p>
        </div>
        <button className="primary" onClick={() => setShow(true)}>
          <Plus size={17} />
          记录购买
        </button>
      </div>
      <PageGuide area={kind} />
      <ErrorNotice error={query.error} />
      <section className="panel">
        <div className="panel-toolbar filters">
          {kind === "services" && (
            <SearchBox
              value={q}
              onChange={(v) => {
                setQ(v);
                setPage(1);
              }}
            />
          )}
          <select
            aria-label="按客户筛选"
            value={customer}
            onChange={(e) => {
              setCustomer(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部客户</option>
            {customers.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            aria-label="按渠道筛选"
            value={supplier}
            onChange={(e) => {
              setSupplier(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部渠道</option>
            {suppliers.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            aria-label="按商品筛选"
            value={product}
            onChange={(e) => {
              setProduct(e.target.value);
              setPage(1);
            }}
          >
            <option value="">全部商品</option>
            {products.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          {kind === "services" && (
            <select
              aria-label="按状态筛选"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">全部状态</option>
              {[
                "active",
                "today",
                "overdue",
                "no_expiry",
                "ended",
                "upcoming",
              ].map((v) => (
                <option value={v} key={v}>
                  {
                    {
                      active: "使用中",
                      today: "今天到期",
                      overdue: "已逾期",
                      no_expiry: "无固定期限",
                      ended: "已结束",
                      upcoming: "未开始",
                    }[v]
                  }
                </option>
              ))}
            </select>
          )}
          <input
            aria-label="起始日期"
            type="date"
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
              setPage(1);
            }}
          />
          <span>至</span>
          <input
            aria-label="截止日期"
            type="date"
            value={to}
            onChange={(e) => {
              setTo(e.target.value);
              setPage(1);
            }}
          />
        </div>
        {query.isPending ? (
          <div className="loading">正在读取记录…</div>
        ) : kind === "services" ? (
          <ServiceTable rows={(query.data?.results || []) as Service[]} />
        ) : (
          <SaleTable
            rows={(query.data?.results || []) as Sale[]}
            onSelect={setSelected}
          />
        )}
        <Pager page={page} total={query.data?.count || 0} onChange={setPage} />
      </section>
      {(show || adding) && <SaleForm onClose={closePurchase} />}
      {selected && (
        <SaleDetail sale={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}
export function CustomerDetail() {
  const { id } = useParams();
  const [show, setShow] = useState(false);
  const customer = useQuery({
    queryKey: ["customer", id],
    queryFn: () => request<Customer>("/customers/" + id + "/"),
  });
  const services = useQuery({
    queryKey: ["customer-services", id],
    queryFn: () => all<Service>("/services/?customer_id=" + id),
  });
  const sales = useQuery({
    queryKey: ["customer-sales", id],
    queryFn: () => all<Sale>("/sales/?customer_id=" + id),
  });
  if (customer.isPending) return <div className="loading">正在读取客户…</div>;
  if (!customer.data) return <ErrorNotice error={customer.error} />;
  const c = customer.data;
  return (
    <>
      <Link className="back" to="/customers">
        <ArrowLeft size={16} />
        客户列表
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">CUSTOMER PROFILE</span>
          <h1>{c.name}</h1>
          <p>{c.notes || "每一次订阅，都有完整记录。"}</p>
        </div>
        <button className="primary" onClick={() => setShow(true)}>
          <Plus size={17} />
          记录购买
        </button>
      </div>
      <div className="contact-strip">
        {c.contacts.length ? (
          c.contacts.map((v, i) => (
            <div key={i}>
              <span>{v.kind === "wechat" ? "微信" : v.kind}</span>
              <strong>{v.value}</strong>
            </div>
          ))
        ) : (
          <span className="muted">尚未填写联系方式，联系续费前请补充。</span>
        )}
      </div>
      <section className="panel">
        <div className="panel-title">
          <h2>客户服务</h2>
          <span>{services.data?.length || 0} 项</span>
        </div>
        <ErrorNotice error={services.error} />
        <ServiceTable rows={services.data || []} />
      </section>
      <section className="panel">
        <div className="panel-title">
          <h2>购买与续费历史</h2>
        </div>
        <ErrorNotice error={sales.error} />
        <SaleTable rows={sales.data || []} />
      </section>
      {show && <SaleForm customerId={c.id} onClose={() => setShow(false)} />}
    </>
  );
}
export function ServiceDetail() {
  const { id } = useParams();
  const cache = useQueryClient();
  const [mode, setMode] = useState<"renewal" | "topup" | null>(null),
    [ending, setEnding] = useState(false),
    [error, setError] = useState<unknown>(null),
    [selected, setSelected] = useState<Sale | null>(null);
  const query = useQuery({
    queryKey: ["service", id],
    queryFn: () => request<Service>("/services/" + id + "/"),
  });
  const history = useQuery({
    queryKey: ["service-sales", id],
    queryFn: () => all<Sale>("/sales/?service_id=" + id),
  });
  if (query.isPending) return <div className="loading">读取服务…</div>;
  if (!query.data) return <ErrorNotice error={query.error} />;
  const s = query.data;
  async function end() {
    try {
      await mutate("/services/" + id + "/end/", {
        expected_revision: s.revision,
      });
      await cache.invalidateQueries();
      setEnding(false);
    } catch (e) {
      setError(e);
    }
  }
  return (
    <>
      <Link className="back" to={"/customers/" + s.customer_id}>
        <ArrowLeft size={16} />
        {s.customer_name}
      </Link>
      <div className="page-heading">
        <div>
          <span className="eyebrow">SERVICE DETAILS · #{s.id}</span>
          <h1>{s.product_name}</h1>
          <p>
            {s.identifier || "未设置服务标识"} · {s.supplier_name}
          </p>
        </div>
        <div className="button-group">
          <button className="secondary" onClick={() => setMode("topup")}>
            追加额度
          </button>
          <button className="primary" onClick={() => setMode("renewal")}>
            <RefreshCw size={16} />
            记录续费
          </button>
        </div>
      </div>
      <div className="detail-grid">
        <div>
          <small>当前状态</small>
          <Badge status={s.status} />
        </div>
        <div>
          <small>开始日期</small>
          <strong>{s.started_on}</strong>
        </div>
        <div>
          <small>到期日期</small>
          <strong>{s.expires_on || "无固定期限"}</strong>
        </div>
        <div>
          <small>累计购买额度</small>
          <strong>
            {s.quota_unit ? s.purchased_quota + " " + s.quota_unit : "—"}
          </strong>
        </div>
      </div>
      <ErrorNotice error={error} />
      <section className="panel">
        <div className="panel-title">
          <h2>交易历史</h2>
          {!s.ended_at && (
            <button
              className="text-button danger-text"
              onClick={() => setEnding(true)}
            >
              结束服务
            </button>
          )}
        </div>
        <SaleTable rows={history.data || []} onSelect={setSelected} />
      </section>
      {s.notes && <div className="notice">{s.notes}</div>}
      {mode && (
        <SaleForm service={s} kind={mode} onClose={() => setMode(null)} />
      )}{" "}
      {ending && (
        <Dialog title="确认结束服务" onClose={() => setEnding(false)}>
          <p>
            「{s.product_name}
            」将停止生成新的到期提醒。历史交易及利润记录会保留。
          </p>
          <ErrorNotice error={error} />
          <footer className="form-footer">
            <button className="secondary" onClick={() => setEnding(false)}>
              取消
            </button>
            <button className="primary" onClick={end}>
              确认结束
            </button>
          </footer>
        </Dialog>
      )}
      {selected && (
        <SaleDetail sale={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}
export function SaleForm({
  onClose,
  customerId,
  service,
  kind = "purchase",
}: {
  onClose: () => void;
  customerId?: number;
  service?: Service;
  kind?: "purchase" | "renewal" | "topup";
}) {
  const cache = useQueryClient(),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const customers = useQuery({
    queryKey: ["customer-options"],
    queryFn: () => all<Customer>("/customers/"),
  });
  const products = useQuery({
    queryKey: ["product-options"],
    queryFn: () => all<Product>("/products/"),
  });
  const [values, setValues] = useState({
    customer_id: String(service?.customer_id || customerId || ""),
    product_id: String(service?.product_id || ""),
    sold_on: localDay(),
    started_on: localDay(),
    expires_on: "",
    term_count: kind === "topup" ? "" : "1",
    term_unit: "month",
    cost: "0",
    price: "0",
    quota_amount: "",
    quota_unit: service?.quota_unit || "",
    identifier: service?.identifier || "",
    notes: "",
  });
  const [submission] = useState(newSubmissionId);
  const set = (key: string, value: string) =>
    setValues((old) => ({ ...old, [key]: value }));
  function choose(id: string) {
    const p = products.data?.find((p) => p.id === Number(id));
    setValues((old) => ({
      ...old,
      product_id: id,
      cost: p ? String(p.cost_fen / 100) : old.cost,
      price: p ? String(p.price_fen / 100) : old.price,
      term_count:
        kind === "topup" ? "" : p?.term_count ? String(p.term_count) : "",
      term_unit: p?.term_unit || "month",
      quota_amount: p?.quota_amount || "",
      quota_unit: p?.quota_unit || service?.quota_unit || "",
    }));
  }
  useEffect(() => {
    if (service && products.data) {
      const p = products.data.find((p) => p.id === service.product_id);
      if (p)
        setValues((old) => ({
          ...old,
          cost: String(p.cost_fen / 100),
          price: String(p.price_fen / 100),
          term_count:
            kind === "topup" ? "" : p.term_count ? String(p.term_count) : "",
          term_unit: p.term_unit || "month",
        }));
    }
  }, [products.data, service?.id]);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = {
        customer_id: Number(values.customer_id),
        product_id: Number(values.product_id),
        sold_on: values.sold_on,
        started_on: kind === "purchase" ? values.started_on : null,
        expires_on: values.expires_on || null,
        term_count: values.term_count ? Number(values.term_count) : null,
        term_unit: values.term_count ? values.term_unit : null,
        quota_amount: values.quota_amount || null,
        quota_unit: values.quota_unit || null,
        identifier: values.identifier,
        notes: values.notes,
        cost_fen: yuan(values.cost),
        price_fen: yuan(values.price),
        submission_id: submission,
        expected_revision: service?.revision,
      };
      await mutate(
        kind === "purchase"
          ? "/sales/"
          : `/services/${service!.id}/${kind === "renewal" ? "renew" : "topup"}/`,
        data,
      );
      await cache.invalidateQueries();
      onClose();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  let profit = "—";
  try {
    profit = money(yuan(values.price) - yuan(values.cost));
  } catch {}
  const base =
    kind === "renewal" &&
    service?.expires_on &&
    service.expires_on > values.sold_on
      ? service.expires_on
      : kind === "purchase"
        ? values.started_on
        : values.sold_on;
  const predicted =
    values.expires_on ||
    previewExpiry(base, values.term_count, values.term_unit);
  const field = (
    key: keyof typeof values,
    label: string,
    type = "text",
    required = false,
  ) => (
    <Field key={key} label={label}>
      <input
        type={type}
        required={required}
        value={values[key]}
        onChange={(e) => set(key, e.target.value)}
      />
    </Field>
  );
  const missingCustomer =
    !customers.isPending &&
    !customers.error &&
    !customers.data?.some((c) => !c.archived_at);
  const missingProduct =
    !products.isPending &&
    !products.error &&
    !products.data?.some((p) => p.is_active);
  if (kind === "purchase" && (missingCustomer || missingProduct))
    return (
      <Dialog title="购买前先准备这些资料" onClose={onClose}>
        <div className="purchase-prerequisites">
          <CircleHelp size={28} />
          <h3>完成基础资料后，就能记录购买</h3>
          <p>每笔购买需要关联一位客户和一个已启用的商品。</p>
          {missingCustomer && (
            <Link className="secondary" to="/customers?new=1">
              添加客户
              <ArrowRight size={16} />
            </Link>
          )}
          {missingProduct && (
            <Link className="secondary" to="/products">
              去完善并启用商品
              <ArrowRight size={16} />
            </Link>
          )}
          <Link className="text-button" to="/guide">
            查看完整使用指南
          </Link>
        </div>
      </Dialog>
    );
  return (
    <Dialog
      title={
        kind === "purchase"
          ? "记录购买"
          : kind === "renewal"
            ? "记录续费"
            : "追加购买额度"
      }
      onClose={onClose}
      wide
    >
      <form onSubmit={save} className="structured-form">
        <div className="form-body">
          <p className="form-intro">
            先选择客户与商品，再核对本次实际收支。
            <span>必填项已标明；到期日期可按期限计算，也可手动指定。</span>
          </p>
          <ErrorNotice error={error || customers.error || products.error} />
          <FormSection
            title="客户与商品"
            step="01"
            description="确认本次交易对应的客户、商品与账号。"
          >
            <Field label="购买客户">
              <select
                required
                disabled={!!service}
                value={values.customer_id}
                onChange={(e) => set("customer_id", e.target.value)}
              >
                <option value="">请选择客户</option>
                {customers.data
                  ?.filter(
                    (c) => !c.archived_at || c.id === service?.customer_id,
                  )
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="购买商品">
              <select
                required
                value={values.product_id}
                onChange={(e) => choose(e.target.value)}
              >
                <option value="">请选择商品</option>
                {products.data
                  ?.filter((p) => p.is_active)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} · {p.supplier_name}
                    </option>
                  ))}
              </select>
            </Field>
            {field("identifier", "账号 / 席位标识")}
          </FormSection>
          <FormSection
            title="本次收支"
            step="02"
            description="填写实际金额，系统据此计算差价利润。"
          >
            {field("sold_on", "成交日期", "date", true)}
            {field("cost", "实际采购成本（元）", "text", true)}
            {field("price", "实际销售金额（元）", "text", true)}
          </FormSection>
          <FormSection
            title="服务期限"
            step="03"
            description="指定到期日优先；续费前请核对上游是否覆盖剩余时长。"
          >
            {kind === "purchase" &&
              field("started_on", "服务开始日期", "date", true)}
            {field("term_count", "期限数量（无期限可留空）", "number")}
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
            {field("expires_on", "指定到期日（可选）", "date")}
          </FormSection>
          <FormSection
            title="额度与备注"
            description="按量商品请填写额度和单位，其他交易可留空。"
            collapsible={kind !== "topup"}
          >
            {field("quota_amount", "本次购买额度")}
            {field("quota_unit", "额度单位")}
            <Field label="交易备注" wide>
              <textarea
                value={values.notes}
                onChange={(e) => set("notes", e.target.value)}
              />
            </Field>
          </FormSection>
          <div className="sale-summary">
            <div>
              <span>本次差价利润</span>
              <strong>{profit}</strong>
            </div>
            <small>
              {kind === "topup"
                ? "累计购买量不代表剩余额度。"
                : `预计到期：${predicted || "无固定期限"}；从 ${base} 计算，指定日期优先。`}
            </small>
          </div>
        </div>
        <footer className="form-footer">
          <button type="button" className="secondary" onClick={onClose}>
            取消
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "正在保存…" : "保存交易"}
          </button>
        </footer>
      </form>
    </Dialog>
  );
}
function SaleDetail({ sale, onClose }: { sale: Sale; onClose: () => void }) {
  const [mode, setMode] = useState<"correct" | "void" | null>(null),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const cache = useQueryClient();
  const service = useQuery({
    queryKey: ["service", String(sale.service_id)],
    queryFn: () => request<Service>(`/services/${sale.service_id}/`),
  });
  const [values, setValues] = useState({
    reason: "",
    cost: String(sale.cost_fen / 100),
    price: String(sale.price_fen / 100),
    sold_on: sale.sold_on,
    expires_on: "",
    ended: false,
    quota: "0",
  });
  function change(m: "correct" | "void") {
    setMode(m);
    setValues((v) => ({
      ...v,
      expires_on: service.data?.expires_on || "",
      ended: !!service.data?.ended_at,
      quota: service.data?.purchased_quota || "0",
    }));
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!service.data) return;
    setBusy(true);
    try {
      await mutate(`/sales/${sale.id}/${mode}/`, {
        reason: values.reason,
        cost_fen: yuan(values.cost),
        price_fen: yuan(values.price),
        sold_on: values.sold_on,
        expected_revision: service.data.revision,
        service_state: {
          expires_on: values.expires_on || null,
          ended: values.ended,
          purchased_quota: values.quota,
        },
      });
      await cache.invalidateQueries();
      onClose();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={"交易详情 · #" + sale.id} onClose={onClose}>
      <div className="receipt">
        <h3>{sale.snapshot.product_name}</h3>
        <p>
          {sale.snapshot.customer_name} · {sale.sold_on}
        </p>
        <dl>
          <dt>采购成本</dt>
          <dd>{money(sale.cost_fen)}</dd>
          <dt>销售金额</dt>
          <dd>{money(sale.price_fen)}</dd>
          <dt>差价利润</dt>
          <dd>{money(sale.price_fen - sale.cost_fen)}</dd>
          <dt>成交时上游</dt>
          <dd>{sale.snapshot.supplier_name}</dd>
          <dt>交付方式</dt>
          <dd>{sale.snapshot.delivery || "—"}</dd>
          <dt>本次到期日</dt>
          <dd>{sale.snapshot.expires_on || "无固定期限"}</dd>
          <dt>质保说明</dt>
          <dd>{sale.snapshot.warranty_notes || "—"}</dd>
          <dt>修改次数</dt>
          <dd>{sale.snapshot.correction_history?.length || 0}</dd>
        </dl>
        {sale.voided_at && (
          <div className="notice">已作废：{sale.void_reason}</div>
        )}
      </div>
      <ErrorNotice error={error || service.error} />
      {mode ? (
        <form onSubmit={save}>
          <div className="notice">
            请核对服务当前状态。修改历史交易不会自动回滚后续续费。
          </div>
          <div className="form-grid">
            {mode === "correct" && (
              <>
                <Field label="实际成本（元）">
                  <input
                    required
                    value={values.cost}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, cost: e.target.value }))
                    }
                  />
                </Field>
                <Field label="实际售价（元）">
                  <input
                    required
                    value={values.price}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, price: e.target.value }))
                    }
                  />
                </Field>
                <Field label="成交日期">
                  <input
                    type="date"
                    required
                    value={values.sold_on}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, sold_on: e.target.value }))
                    }
                  />
                </Field>
              </>
            )}
            <Field label="服务保留的到期日">
              <input
                type="date"
                value={values.expires_on}
                onChange={(e) =>
                  setValues((v) => ({ ...v, expires_on: e.target.value }))
                }
              />
            </Field>
            <Field label="服务累计购买额度">
              <input
                required
                value={values.quota}
                onChange={(e) =>
                  setValues((v) => ({ ...v, quota: e.target.value }))
                }
              />
            </Field>
            <label className="check">
              <input
                type="checkbox"
                checked={values.ended}
                onChange={(e) =>
                  setValues((v) => ({ ...v, ended: e.target.checked }))
                }
              />
              服务已结束
            </label>
            <Field label="修改原因">
              <textarea
                required
                value={values.reason}
                onChange={(e) =>
                  setValues((v) => ({ ...v, reason: e.target.value }))
                }
              />
            </Field>
          </div>
          <footer className="form-footer">
            <button
              type="button"
              className="secondary"
              onClick={() => setMode(null)}
            >
              返回
            </button>
            <button className="primary" disabled={busy}>
              确认{mode === "void" ? "作废" : "纠错"}
            </button>
          </footer>
        </form>
      ) : (
        !sale.voided_at && (
          <footer className="form-footer">
            <button
              className="secondary danger-text"
              disabled={!service.data}
              onClick={() => change("void")}
            >
              作废交易
            </button>
            <button
              className="primary"
              disabled={!service.data}
              onClick={() => change("correct")}
            >
              纠正记录
            </button>
          </footer>
        )
      )}
    </Dialog>
  );
}
