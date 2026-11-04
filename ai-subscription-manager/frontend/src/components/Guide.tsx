import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  CircleHelp,
  ChevronDown,
  BookOpen,
} from "lucide-react";
import { all, request } from "../api/client";
import type { Supplier, Product, Customer, MailSettings } from "../api/types";
import { ErrorNotice } from "./ui";

type Area =
  "suppliers" | "products" | "customers" | "services" | "sales" | "reminders";
const help: Record<
  Area,
  { title: string; points: string[]; next: string; to: string }
> = {
  suppliers: {
    title: "上游渠道：记录你向谁拿货",
    points: [
      "一家商家建一条渠道，填写店铺链接、微信或 QQ 和售后规则。",
      "已有导入渠道可直接编辑补充；标注“待验证”表示还没完成试单。",
      "渠道保存后，到商品目录关联这个商家，并填写你打算销售的套餐。",
    ],
    next: "下一步：整理商品",
    to: "/products",
  },
  products: {
    title: "商品目录：定义你卖什么、从哪里拿货",
    points: [
      "同一套餐的不同上游或交付方式，可分别建商品；采购价是你付上游的钱，售价是客户付给你的钱。",
      "导入商品暂时停用、售价以 0 占位：先点“编辑”确认价格、期限和质保，再点“启用”并确认。停用商品不会出现在新购买的选项中。",
      "保存商品只是建立销售模板，不会创建客户订阅，也不会计入利润。实际成交后还要“记录购买”。",
    ],
    next: "下一步：添加客户",
    to: "/customers?new=1",
  },
  customers: {
    title: "客户管理：记录谁向你购买",
    points: [
      "点“添加客户”，填写姓名或昵称；微信、QQ、电话按实际情况选填，建议至少留一种联系方式。",
      "保存后点击客户名字进入详情，再点“记录购买”，关联已启用的商品。",
      "同一客户可以有多项订阅，用账号或席位标识区分；客户资料本身不产生交易和到期提醒。",
    ],
    next: "下一步：记录购买",
    to: "/services?new=1",
  },
  services: {
    title: "订阅与服务：看每个客户什么时候到期",
    points: [
      "首次成交点“记录购买”：选择客户和商品，填写实际成本、实收金额、开始日期和期限。",
      "系统会生成一项服务并计算到期日；上游若按覆盖充值处理，请以实际到账日为准手动指定到期日。",
      "老客户续费：找到原服务，点“查看”进入详情，再点“记录续费”。同一项服务不用重新创建。",
    ],
    next: "查看邮件提醒设置",
    to: "/reminders",
  },
  sales: {
    title: "交易记录：核对每次成交的收入和成本",
    points: [
      "购买、续费和追加额度都会自动记入账本，无需重复录入。",
      "差价利润 = 实际销售金额 − 实际采购成本；统计按成交日期计算。",
      "金额或日期填错时点“详情”再选“纠正记录”；作废会影响账本及服务状态，请核对后操作。",
    ],
    next: "去查看客户订阅",
    to: "/services",
  },
  reminders: {
    title: "邮件提醒：提醒你联系客户续费",
    points: [
      "这里填写你接收通知的邮箱，邮件发给你，不会自动发给客户或通过微信、QQ联系客户。",
      "有到期日的服务会在到期前 3 天、当天提醒，每天上午 9 点汇总，并定时检查补发。",
      "收到提醒后联系客户；成交后回原服务登记续费，系统会更新后续提醒。可用“发送测试邮件”检查投递。",
    ],
    next: "去查看到期服务",
    to: "/services",
  },
};
export function PageGuide({ area }: { area: Area }) {
  const guide = help[area];
  return (
    <details className="page-guide">
      <summary>
        <CircleHelp size={18} />
        <span>{guide.title}</span>
        <small>本页怎么用</small>
        <ChevronDown size={16} />
      </summary>
      <div className="page-guide-body">
        <ol>
          {guide.points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ol>
        <div className="guide-links">
          <Link to={guide.to}>
            {guide.next}
            <ArrowRight size={15} />
          </Link>
          <Link to="/guide">完整使用指南</Link>
        </div>
      </div>
    </details>
  );
}
export function GettingStarted({ serviceCount }: { serviceCount?: number }) {
  const suppliers = useQuery({
    queryKey: ["supplier-options"],
    queryFn: () => all<Supplier>("/suppliers/"),
  });
  const products = useQuery({
    queryKey: ["product-options"],
    queryFn: () => all<Product>("/products/"),
  });
  const customers = useQuery({
    queryKey: ["customer-options"],
    queryFn: () => all<Customer>("/customers/"),
  });
  const mail = useQuery({
    queryKey: ["reminder-settings"],
    queryFn: () => request<MailSettings>("/reminders/settings/"),
  });
  const error =
    suppliers.error || products.error || customers.error || mail.error;
  const pending =
    suppliers.isPending ||
    products.isPending ||
    customers.isPending ||
    mail.isPending ||
    serviceCount === undefined;
  if (error)
    return (
      <section className="start-guide">
        <h2>使用引导暂时无法读取</h2>
        <ErrorNotice error={error} />
        <Link to="/guide">查看操作说明</Link>
      </section>
    );
  if (pending)
    return (
      <section className="start-guide" aria-busy="true">
        <p>正在根据已有记录整理下一步…</p>
      </section>
    );
  const activeSuppliers = new Set(
    suppliers.data?.filter((s) => s.is_active).map((s) => s.id),
  );
  const saleable =
    products.data?.filter(
      (p) =>
        p.is_active && p.price_fen > 0 && activeSuppliers.has(p.supplier_id),
    ) || [];
  const activeCustomers = customers.data?.filter((c) => !c.archived_at) || [];
  const steps = [
    {
      title: "确认供货渠道",
      done: activeSuppliers.size > 0,
      detail: "留下商家联系方式与采购规则",
      to: activeSuppliers.size ? "/suppliers" : "/suppliers?new=1",
      action: "添加第一个上游",
      description:
        "先记录一家你准备采购的商家。渠道名称必填，网址和联系方式可以继续补充。",
    },
    {
      title: "定价并启用商品",
      done: saleable.length > 0,
      detail: "确认成本、售价与订阅期限",
      to: products.data?.length ? "/products" : "/products?new=1",
      action: products.data?.length ? "去完善并启用商品" : "添加第一个商品",
      description: products.data?.length
        ? "已有商品资料。先到商品目录点“编辑”填写售价、核对期限与质保，再点“启用”。导入商品的 0 元售价是待定占位。"
        : "选择上游，填写商品名称、参考成本和售价。一个商品就是一份可重复使用的销售模板。",
    },
    {
      title: "添加客户",
      done: activeCustomers.length > 0,
      detail: "保存客户称呼、微信或 QQ",
      to: "/customers?new=1",
      action: "添加第一位客户",
      description:
        "先添加一位真实客户，记录姓名或昵称，建议填写微信或 QQ，方便收到到期邮件后联系。",
    },
    {
      title: "记录首笔购买",
      done: (serviceCount || 0) > 0,
      detail: "生成订阅、到期日与交易记录",
      to: "/services?new=1",
      action: "记录第一笔购买",
      description:
        "选好客户和商品，核对实际采购成本、实收金额、开始时间和期限。保存后，订阅、账本和到期提醒会联动建立。",
    },
  ];
  const next = steps.findIndex((s) => !s.done);
  const complete = next === -1;
  const ready = !!mail.data?.mail_ready && !!mail.data.recipient;
  const current = complete
    ? {
        action: "查看订阅与续费",
        to: "/services",
        description:
          "平时看首页的续费待办；客户续费后，进入原服务登记“记录续费”，不用重新添加客户或商品。",
      }
    : steps[next];
  return (
    <section className="start-guide" aria-labelledby="start-guide-title">
      <div className="start-guide-main">
        <div>
          <span className="start-guide-kicker">
            {complete ? "日常经营" : "从这里开始"} ·{" "}
            {steps.filter((s) => s.done).length}/4 项已就绪
          </span>
          <h2 id="start-guide-title">
            {complete
              ? "基础资料已就绪，接下来跟进订阅与续费"
              : "下一步：" + steps[next].title}
          </h2>
          <p>{current.description}</p>
        </div>
        <Link className="primary" to={current.to}>
          {current.action}
          <ArrowRight size={16} />
        </Link>
      </div>
      <ol className="start-guide-steps">
        {steps.map((step, index) => (
          <li
            key={step.title}
            className={step.done ? "done" : index === next ? "current" : ""}
          >
            <Link
              to={step.to}
              aria-current={index === next ? "step" : undefined}
            >
              <span className="guide-step-number">
                {step.done ? <CheckCircle2 size={20} /> : index + 1}
              </span>
              <span>
                <strong>{step.title}</strong>
                <small>{step.detail}</small>
              </span>
            </Link>
          </li>
        ))}
      </ol>
      <div className="start-guide-foot">
        <span>
          <span className={"guide-dot " + (ready ? "ready" : "")} />
          {ready
            ? "提醒邮箱已保存，邮件服务已配置；可发测试邮件验证"
            : "邮件提醒尚未就绪，请检查接收邮箱与邮件服务"}
        </span>
        <Link to="/reminders">检查提醒设置</Link>
        <Link to="/guide">
          <BookOpen size={14} />
          完整使用指南
        </Link>
      </div>
    </section>
  );
}
export function GuidePage() {
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">WORKSPACE GUIDE</span>
          <h1>使用指南</h1>
          <p>按这个顺序，把一笔真实业务完整记下来。</p>
        </div>
        <Link className="secondary" to="/">
          返回经营概览
        </Link>
      </div>
      <section className="guide-overview">
        <h2>上游 → 商品 → 客户 → 购买 → 续费</h2>
        <p>
          你只需录一次基础资料。每次成交登记实际金额和期限，系统负责记账、计算到期日与安排提醒。
        </p>
        <strong>
          记住：添加商品 ≠
          已售出。点“记录购买”保存交易后，才会产生客户订阅和利润。
        </strong>
      </section>
      <div className="guide-manual">
        {(Object.entries(help) as [Area, (typeof help)[Area]][]).map(
          ([area, item], index) => (
            <section className="panel guide-manual-section" key={area}>
              <span className="form-step">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <h2>{item.title}</h2>
                <ol>
                  {item.points.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ol>
                <Link className="text-button" to={"/" + area}>
                  打开
                  {area === "suppliers"
                    ? "上游渠道"
                    : area === "products"
                      ? "商品目录"
                      : area === "customers"
                        ? "客户管理"
                        : area === "services"
                          ? "订阅与服务"
                          : area === "sales"
                            ? "交易记录"
                            : "邮件提醒"}
                  <ArrowRight size={15} />
                </Link>
              </div>
            </section>
          ),
        )}
      </div>
      <section className="panel guide-example">
        <h2>举个例子：客户买 1 个月的 Plus</h2>
        <p>
          先给客户建档，再点“记录购买”。选择对应商品，采购成本填 112.04
          元，实际销售金额按你和客户的成交价填写；期限选择“1 /
          月”，核对到期日后保存。
        </p>
        <p>
          客户下个月再买时，打开这项服务，点“记录续费”。如果上游是覆盖充值，手动填写实际到期日，避免系统按原期限顺延。
        </p>
        <Link className="primary" to="/services?new=1">
          开始记录购买
          <ArrowRight size={16} />
        </Link>
      </section>
    </>
  );
}
