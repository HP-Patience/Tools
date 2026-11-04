import { useEffect, useState, type FormEvent } from "react";
import { NavLink, Routes, Route, useLocation, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  LayoutDashboard,
  Users,
  Network,
  Package,
  Layers3,
  ReceiptText,
  Mail,
  CircleHelp,
  LogOut,
  Menu,
  ArrowUpRight,
  Leaf,
  ShieldCheck,
  X,
} from "lucide-react";
import { request, mutate } from "../api/client";
import { ErrorNotice, Field, localDay } from "../components/ui";
import { GuidePage } from "../components/Guide";
import { Dashboard } from "../features/Dashboard";
import { Catalog } from "../features/Catalog";
import { Records, CustomerDetail, ServiceDetail } from "../features/Billing";
import { Reminders } from "../features/Reminders";
type User = { user: { id: number; username: string } };
const links = [
  { to: "/", label: "经营概览", icon: LayoutDashboard },
  { to: "/customers", label: "客户管理", icon: Users },
  { to: "/suppliers", label: "上游渠道", icon: Network },
  { to: "/products", label: "商品目录", icon: Package },
  { to: "/services", label: "订阅与服务", icon: Layers3 },
  { to: "/sales", label: "交易记录", icon: ReceiptText },
  { to: "/reminders", label: "邮件提醒", icon: Mail },
  { to: "/guide", label: "使用指南", icon: CircleHelp },
];
function Login() {
  const cache = useQueryClient();
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [confirmation, setConfirmation] = useState(""),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const status = useQuery({
    queryKey: ["auth-status"],
    queryFn: () => request<{ needs_setup: boolean }>("/auth/status/"),
    retry: false,
  });
  const needsSetup = status.data?.needs_setup ?? false;
  async function login(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (needsSetup && password !== confirmation)
        throw new Error("两次输入的密码不一致");
      const data = await mutate<User>(
        needsSetup ? "/auth/setup/" : "/auth/login/",
        {
          username,
          password,
          ...(needsSetup ? { confirm_password: confirmation } : {}),
        },
      );
      cache.setQueryData(["auth-status"], { needs_setup: false });
      cache.setQueryData(["me"], data);
      setPassword("");
      setConfirmation("");
    } catch (e) {
      setError(e);
      await cache.invalidateQueries({ queryKey: ["auth-status"] });
    } finally {
      setBusy(false);
    }
  }
  if (status.isPending)
    return (
      <div className="boot">
        <Leaf size={34} />
        <span>正在检查账户设置…</span>
      </div>
    );
  return (
    <main className="login-shell">
      <section className="login-intro">
        <div className="brand">
          <span className="brand-logo">
            <Leaf size={23} />
          </span>
          <div>
            续订<span>SUBSCRIPTION DESK</span>
          </div>
        </div>
        <span className="eyebrow">A CLEARER WAY TO RUN YOUR BUSINESS</span>
        <h1>
          每一次订阅，
          <br />
          都照顾周全。
        </h1>
        <p>
          渠道、客户、成交与续费。
          <br />
          在一个安静有序的工作台里，管理你的 AI 订阅生意。
        </p>
        <div className="login-decoration">
          <span>客户关系</span>
          <span>服务期限</span>
          <span>差价利润</span>
        </div>
        <small>为个人经营者而设计</small>
      </section>
      <section className="login-form">
        <div className="mobile-brand">续订 / SUBSCRIPTION DESK</div>
        <span className="eyebrow">
          {needsSetup ? "SET UP YOUR WORKSPACE" : "WELCOME BACK"}
        </span>
        <h2>{needsSetup ? "设置管理员账户" : "登录你的工作台"}</h2>
        <p>
          {needsSetup
            ? "第一次使用，请设置你的管理员账号和密码。"
            : "把琐事理清，开始今天的经营。"}
        </p>
        <form onSubmit={login}>
          <ErrorNotice error={error || status.error} />
          <Field label="用户名">
            <input
              autoFocus
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </Field>
          <Field label="密码">
            <input
              type="password"
              autoComplete={needsSetup ? "new-password" : "current-password"}
              minLength={needsSetup ? 12 : undefined}
              maxLength={128}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          {needsSetup && (
            <Field label="确认密码" hint="密码至少 12 位，请妥善保存。">
              <input
                type="password"
                required
                minLength={12}
                maxLength={128}
                autoComplete="new-password"
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
              />
            </Field>
          )}
          <button className="primary" disabled={busy || status.isError}>
            {busy
              ? "正在验证…"
              : needsSetup
                ? "创建管理员并进入"
                : "登录工作台"}
            <ArrowUpRight size={18} />
          </button>
        </form>
        <div className="login-security">
          <ShieldCheck size={16} />
          {needsSetup
            ? "仅首次设置开放，创建后自动关闭"
            : "仅管理员本人使用，无公开注册入口"}
        </div>
      </section>
    </main>
  );
}
export function App() {
  const cache = useQueryClient();
  const [menu, setMenu] = useState(false),
    [error, setError] = useState<unknown>(null);
  const location = useLocation();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => request<User>("/auth/me/"),
    retry: false,
    staleTime: 300000,
  });
  useEffect(() => {
    const expire = () => {
      cache.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
      cache.setQueryData(["me"], null);
    };
    window.addEventListener("auth-expired", expire);
    return () => window.removeEventListener("auth-expired", expire);
  }, [cache]);
  useEffect(() => setMenu(false), [location.pathname]);
  async function logout() {
    try {
      await mutate("/auth/logout/", {});
      cache.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
      cache.setQueryData(["me"], null);
    } catch (e) {
      setError(e);
    }
  }
  if (me.isPending)
    return (
      <div className="boot">
        <Leaf size={34} />
        <span>正在打开工作台…</span>
      </div>
    );
  if (!me.data?.user) return <Login />;
  const active = links.find((l) =>
    l.to === "/"
      ? location.pathname === "/"
      : location.pathname.startsWith(l.to),
  );
  return (
    <div className="app-shell">
      {menu && <div className="nav-scrim" onClick={() => setMenu(false)} />}
      <aside className={"sidebar " + (menu ? "open" : "")}>
        <Link to="/" className="brand">
          <span className="brand-logo">
            <Leaf size={23} />
          </span>
          <div>
            续订<span>SUBSCRIPTION DESK</span>
          </div>
        </Link>
        <div className="workspace-tag">
          <span className="live-dot" />
          个人经营工作台<span>01</span>
        </div>
        <span className="nav-caption">工作空间</span>
        <nav>
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.to === "/"}>
              <l.icon size={18} strokeWidth={1.7} />
              <span>{l.label}</span>
              {l.to === "/reminders" && <span className="nav-small-dot" />}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="side-note">
            <Leaf size={20} />
            <p>
              好的服务，
              <br />
              值得每一次续订。
            </p>
          </div>
          <div className="owner-card">
            <span className="avatar">管</span>
            <div>
              <strong>{me.data.user.username}</strong>
              <small>管理员 · 个人空间</small>
            </div>
            <button
              aria-label="退出登录"
              className="icon-button"
              onClick={logout}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="打开导航"
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span>工作空间</span>
            <i>/</i>
            <strong>{active?.label || "详情"}</strong>
          </div>
          <div className="topbar-right">
            <span className="top-date">
              {localDay().replaceAll("-", " / ")}
            </span>
            <span className="private-label">
              <ShieldCheck size={14} />
              私有工作台
            </span>
          </div>
        </header>
        <main className="content">
          <ErrorNotice error={error} />
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/customers" element={<Catalog kind="customers" />} />
            <Route path="/customers/:id" element={<CustomerDetail />} />
            <Route path="/suppliers" element={<Catalog kind="suppliers" />} />
            <Route path="/products" element={<Catalog kind="products" />} />
            <Route path="/services" element={<Records kind="services" />} />
            <Route path="/services/:id" element={<ServiceDetail />} />
            <Route path="/sales" element={<Records kind="sales" />} />
            <Route path="/reminders" element={<Reminders />} />
            <Route path="/guide" element={<GuidePage />} />
            <Route
              path="*"
              element={
                <div className="empty">
                  <h1>页面不存在</h1>
                  <Link to="/">返回经营概览</Link>
                </div>
              }
            />
          </Routes>
          <footer className="page-footer">
            <span>续订 · 让经营有迹可循</span>
            <span>PRIVATE WORKSPACE</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
