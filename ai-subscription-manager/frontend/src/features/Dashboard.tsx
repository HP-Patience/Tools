import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Plus,
  ArrowUpRight,
  CalendarClock,
  ArrowRight,
  Wallet,
  TrendingUp,
  Users,
  Layers3,
} from "lucide-react";
import { request } from "../api/client";
import type { Dashboard as Data } from "../api/types";
import { money, localDay, Badge, ErrorNotice, Empty } from "../components/ui";
import { GettingStarted } from "../components/Guide";
import { SaleForm, SaleTable } from "./Billing";
export function Dashboard() {
  const [month, setMonth] = useState(localDay().slice(0, 7)),
    [show, setShow] = useState(false);
  const q = useQuery({
    queryKey: ["dashboard", month],
    queryFn: () => request<Data>("/dashboard/?month=" + month),
  });
  const d = q.data;
  const profit = d?.totals.profit_fen || 0;
  const cards = [
    {
      label: "本月销售金额",
      value: money(d?.totals.revenue_fen || 0),
      icon: Wallet,
      detail: "按成交日期统计",
      className: "",
    },
    {
      label: "本月差价利润",
      value: money(profit),
      icon: TrendingUp,
      detail: "销售金额 − 采购成本",
      className: "highlight",
    },
    {
      label: "客户总数",
      value: String(d?.customer_count || 0),
      icon: Users,
      detail: "每一段合作，值得记录",
      className: "",
    },
    {
      label: "在管服务",
      value: String(d?.service_count || 0),
      icon: Layers3,
      detail: "订阅与额度统一管理",
      className: "",
    },
  ];
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR BUSINESS, IN VIEW</span>
          <h1>
            经营概览<span className="title-dot">.</span>
          </h1>
          <p>把续费记在这里，把精力留给客户。</p>
        </div>
        <div className="button-group">
          <input
            aria-label="统计月份"
            className="month-picker"
            type="month"
            value={month}
            onChange={(e) => e.target.value && setMonth(e.target.value)}
          />
          <button className="primary" onClick={() => setShow(true)}>
            <Plus size={17} />
            记录购买
          </button>
        </div>
      </div>
      <ErrorNotice error={q.error} />
      <GettingStarted serviceCount={d?.service_count} />
      <div className="stats-grid">
        {cards.map((c, i) => (
          <article
            className={"stat-card " + c.className}
            key={c.label}
            style={{ animationDelay: i * 60 + "ms" }}
          >
            <div className="stat-top">
              <span>{c.label}</span>
              <c.icon size={18} strokeWidth={1.6} />
            </div>
            <strong>{q.isPending ? "—" : c.value}</strong>
            <small>{c.detail}</small>
          </article>
        ))}
      </div>
      <div className="dashboard-columns">
        <section className="panel due-panel">
          <div className="panel-title">
            <div>
              <span className="eyebrow">FOLLOW UP</span>
              <h2>
                续费待办{" "}
                <span className="count-pill">{d?.due.length || 0}</span>
              </h2>
            </div>
            <Link className="text-button" to="/services">
              全部服务 <ArrowUpRight size={15} />
            </Link>
          </div>
          <div className="due-note">
            <CalendarClock size={16} />
            <span>到期前 3 天和当天提醒，逾期服务继续保留在此。</span>
          </div>
          {q.isPending ? (
            <div className="loading">正在整理待办…</div>
          ) : !d?.due.length ? (
            <Empty message="近期没有需要跟进的服务" />
          ) : (
            <div className="due-list">
              {d.due.map((s) => (
                <Link to={"/services/" + s.id} className="due-row" key={s.id}>
                  <span className="avatar">{s.customer_name.slice(0, 1)}</span>
                  <div className="due-person">
                    <strong>{s.customer_name}</strong>
                    <small>
                      {s.product_name}
                      {s.identifier ? " · " + s.identifier : ""}
                    </small>
                    <span className="contact-line">
                      {s.contacts[0] ? s.contacts[0].value : "未填写联系方式"}
                    </span>
                  </div>
                  <div className="due-date">
                    <Badge status={s.status === "active" ? "soon" : s.status} />
                    <small>{s.expires_on}</small>
                  </div>
                  <ArrowRight size={16} className="muted" />
                </Link>
              ))}
            </div>
          )}
        </section>
        <aside className="overview-aside">
          <div className="operations-card">
            <span className="eyebrow">A SMALL ROUTINE</span>
            <h2>
              生意有序，
              <br />
              续订不漏。
            </h2>
            <p>
              找到好渠道，记下每次成交，
              <br />
              及时跟进下一次续费。
            </p>
            <div className="operations-mark">↗</div>
            <Link to="/suppliers">
              查看我的上游渠道 <ArrowUpRight size={17} />
            </Link>
          </div>
          <div className="mini-panel">
            <span className="eyebrow">THIS MONTH</span>
            <div>
              <span>采购支出</span>
              <strong>{money(d?.totals.cost_fen || 0)}</strong>
            </div>
            <div>
              <span>本月成交</span>
              <strong>
                {d?.sale_count || 0}
                <small> 笔</small>
              </strong>
            </div>
            <Link to="/reminders">
              管理邮件提醒 <ArrowRight size={15} />
            </Link>
          </div>
        </aside>
      </div>
      <section className="panel">
        <div className="panel-title">
          <div>
            <span className="eyebrow">LATEST ACTIVITY</span>
            <h2>最近成交</h2>
          </div>
          <Link className="text-button" to="/sales">
            查看账本 <ArrowUpRight size={15} />
          </Link>
        </div>
        <SaleTable rows={d?.recent_sales || []} />
      </section>
      {show && <SaleForm onClose={() => setShow(false)} />}
    </>
  );
}
