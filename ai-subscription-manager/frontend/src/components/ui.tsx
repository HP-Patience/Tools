import {
  useEffect,
  useRef,
  useId,
  cloneElement,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import {
  X,
  Search,
  ArrowLeft,
  ArrowRight,
  Inbox,
  ChevronDown,
} from "lucide-react";
import { ApiError } from "../api/client";
export const money = (fen: number) =>
  new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY" }).format(
    fen / 100,
  );
export const localDay = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Hong_Kong",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
export function yuan(value: string) {
  if (!/^\d+(\.\d{1,2})?$/.test(value))
    throw new Error("金额必须是非负数字，最多两位小数");
  const [whole, fraction = ""] = value.split(".");
  const result = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  if (!Number.isSafeInteger(result) || result > 999999999999)
    throw new Error("金额超出范围");
  return result;
}
export const statusNames: Record<string, string> = {
  active: "使用中",
  soon: "3 天内到期",
  upcoming: "未开始",
  today: "今天到期",
  overdue: "已逾期",
  ended: "已结束",
  no_expiry: "无固定期限",
  sent: "已发送",
  failed: "发送失败",
  uncertain: "结果待核实",
  claimed: "发送中",
  success: "已完成",
  attention: "需要处理",
};
export function Badge({ status }: { status: string }) {
  return (
    <span className={"badge " + status}>
      <i />
      {statusNames[status] || status}
    </span>
  );
}
export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="notice error" role="alert">
      {error instanceof Error ? error.message : "操作失败"}
      {error instanceof ApiError &&
        Object.entries(error.fields).map(([k, v]) => (
          <small key={k}>
            {k}：{v}
          </small>
        ))}
    </div>
  );
}
export function Field({
  label,
  children,
  hint,
  required,
  wide = false,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
  required?: boolean;
  wide?: boolean;
}) {
  const id = useId();
  const control = isValidElement<{
    required?: boolean;
    "aria-describedby"?: string;
  }>(children)
    ? children
    : null;
  const mandatory = required ?? control?.props.required ?? false;
  return (
    <div className={"field" + (wide ? " field-wide" : "")}>
      <label htmlFor={id}>
        <span id={id + "-label"}>{label}</span>
        <span
          className={"field-status " + (mandatory ? "required" : "optional")}
          aria-hidden="true"
        >
          {mandatory ? "必填" : "选填"}
        </span>
      </label>
      <div>
        {control
          ? cloneElement(
              control as ReactElement<{
                id?: string;
                "aria-labelledby"?: string;
                "aria-describedby"?: string;
              }>,
              {
                id,
                "aria-labelledby": id + "-label",
                "aria-describedby":
                  [control.props["aria-describedby"], hint ? id + "-hint" : ""]
                    .filter(Boolean)
                    .join(" ") || undefined,
              },
            )
          : children}
      </div>
      {hint && <small id={id + "-hint"}>{hint}</small>}
    </div>
  );
}
export function FormSection({
  title,
  description,
  step,
  collapsible = false,
  children,
}: {
  title: string;
  description: string;
  step?: string;
  collapsible?: boolean;
  children: ReactNode;
}) {
  const id = useId();
  const heading = (
    <>
      {step && (
        <span className="form-step" aria-hidden="true">
          {step}
        </span>
      )}
      <div className="form-section-title">
        <span id={id}>{title}</span>
        <p>{description}</p>
      </div>
      {collapsible && (
        <ChevronDown
          className="disclosure-chevron"
          size={18}
          aria-hidden="true"
        />
      )}
    </>
  );
  return collapsible ? (
    <details className="form-section form-disclosure">
      <summary>{heading}</summary>
      <div className="form-grid">{children}</div>
    </details>
  ) : (
    <section className="form-section" aria-labelledby={id}>
      <header>{heading}</header>
      <div className="form-grid">{children}</div>
    </section>
  );
}
export function Dialog({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    const el = ref.current;
    const focusables = () =>
      Array.from(
        el?.querySelectorAll<HTMLElement>(
          "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], summary",
        ) || [],
      ).filter((element) => element.getClientRects().length > 0);
    (
      el?.querySelector<HTMLElement>(
        "input:not([disabled]), select:not([disabled]), textarea:not([disabled])",
      ) || focusables()[0]
    )?.focus();
    const trap = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const f = focusables();
      if (e.shiftKey && document.activeElement === f[0]) {
        e.preventDefault();
        f.at(-1)?.focus();
      } else if (!e.shiftKey && document.activeElement === f.at(-1)) {
        e.preventDefault();
        f[0]?.focus();
      }
    };
    el?.addEventListener("keydown", trap);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      el?.removeEventListener("keydown", trap);
      document.body.style.overflow = overflow;
      before?.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={"modal " + (wide ? "wide" : "")}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
        }}
      >
        <header>
          <div>
            <span className="eyebrow">SUBSCRIPTION DESK</span>
            <h2>{title}</h2>
          </div>
          <button className="icon-button" aria-label="关闭" onClick={onClose}>
            <X size={20} />
          </button>
        </header>
        <div className="dialog-content">{children}</div>
      </section>
    </div>
  );
}
export function Empty({
  message = "还没有记录",
  action,
}: {
  message?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <Inbox size={34} strokeWidth={1.2} />
      <h3>{message}</h3>
      <p>从添加第一条记录开始，让业务有迹可循。</p>
      {action}
    </div>
  );
}
export function SearchBox({
  value,
  onChange,
  placeholder = "搜索名称或联系方式",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="search">
      <Search size={17} />
      <input
        aria-label="搜索"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
export function Pager({
  page,
  total,
  onChange,
}: {
  page: number;
  total: number;
  onChange: (n: number) => void;
}) {
  return (
    <footer className="pager">
      <span>
        共 {total} 条记录 · 第 {page} 页
      </span>
      <div>
        <button
          aria-label="上一页"
          className="icon-button"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ArrowLeft size={16} />
        </button>
        <button
          aria-label="下一页"
          className="icon-button"
          disabled={page * 25 >= total}
          onClick={() => onChange(page + 1)}
        >
          <ArrowRight size={16} />
        </button>
      </div>
    </footer>
  );
}
