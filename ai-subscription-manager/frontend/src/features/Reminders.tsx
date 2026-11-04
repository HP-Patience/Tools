import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, Send, RefreshCw, CheckCircle2, Clock3 } from "lucide-react";
import { request, mutate } from "../api/client";
import type { MailSettings, MailBatch, Run, Page } from "../api/types";
import { Field, ErrorNotice, Badge, Empty, Pager } from "../components/ui";
import { PageGuide } from "../components/Guide";
export function Reminders() {
  const cache = useQueryClient();
  const [email, setEmail] = useState<string | null>(null),
    [error, setError] = useState<unknown>(null),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: ["reminder-settings"],
    queryFn: () => request<MailSettings>("/reminders/settings/"),
  });
  const log = useQuery({
    queryKey: ["reminder-runs", page],
    queryFn: () =>
      request<{ runs: Page<Run>; batches: Page<MailBatch> }>(
        "/reminders/runs/?page=" + page,
      ),
  });
  async function act(kind: "save" | "test" | "retry", e?: FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      const result = await mutate<{ message?: string }>(
        `/reminders/${kind === "save" ? "settings/" : kind + "/"}`,
        kind === "save" ? { recipient: email ?? q.data?.recipient } : {},
        kind === "save" ? "PATCH" : "POST",
      );
      setNotice(
        kind === "save"
          ? "提醒邮箱已保存"
          : result.message || "已执行补发检查，请查看发送记录",
      );
      await cache.invalidateQueries();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">NEVER MISS A RENEWAL</span>
          <h1>邮件提醒</h1>
          <p>到期之前，给自己一个及时的提醒。</p>
        </div>
        <button
          className="secondary"
          disabled={busy}
          onClick={() => act("retry")}
        >
          <RefreshCw size={16} />
          检查并重试
        </button>
      </div>
      <PageGuide area="reminders" />
      <ErrorNotice error={error || q.error || log.error} />
      {notice && (
        <div className="notice success" role="status">
          <CheckCircle2 size={17} />
          {notice}
        </div>
      )}
      <div className="settings-grid">
        <section className="panel settings-panel">
          <div className="panel-title">
            <h2>
              <Mail size={19} /> 接收设置
            </h2>
          </div>
          <form onSubmit={(e) => act("save", e)}>
            <Field label="接收提醒的邮箱" hint="通知发给你，由你联系客户续费。">
              <input
                type="email"
                required
                placeholder="you@example.com"
                value={email ?? q.data?.recipient ?? ""}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <div className="button-group">
              <button className="primary" disabled={busy}>
                保存设置
              </button>
              <button
                type="button"
                className="secondary"
                disabled={busy || !q.data?.recipient}
                onClick={() => act("test")}
              >
                <Send size={15} />
                发送测试邮件
              </button>
            </div>
          </form>
          <div className={"notice " + (q.data?.mail_ready ? "success" : "")}>
            <strong>
              {q.data?.mail_ready ? "邮件服务已配置" : "邮件服务待配置"}
            </strong>
            <p>
              {q.data?.mail_ready
                ? "可以发送测试邮件验证投递。"
                : "请在服务器配置 SMTP 后使用；后台不显示或保存邮件密码。"}
            </p>
          </div>
        </section>
        <section className="panel settings-panel">
          <div className="panel-title">
            <h2>
              <Clock3 size={19} /> 提醒规则
            </h2>
          </div>
          <div className="reminder-rule">
            <span>01</span>
            <div>
              <strong>到期前 3 天</strong>
              <small>提前准备，联系客户确认续费意向。</small>
            </div>
          </div>
          <div className="reminder-rule">
            <span>02</span>
            <div>
              <strong>到期当天</strong>
              <small>再次提醒，及时安排续订。</small>
            </div>
          </div>
          <p className="muted">{q.data?.schedule} · 香港时间</p>
          <p className="muted">
            最近扫描：
            {q.data?.last_run
              ? new Date(q.data.last_run.started_at + "Z").toLocaleString(
                  "zh-CN",
                )
              : "尚未运行"}
          </p>
        </section>
      </div>
      <section className="panel">
        <div className="panel-title">
          <h2>邮件发送记录</h2>
          <span className="muted">投递结果不确定时请核实邮箱</span>
        </div>
        {!log.data?.batches.results.length ? (
          <Empty message="尚无邮件发送记录" />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>接收邮箱</th>
                  <th>状态</th>
                  <th>尝试次数</th>
                  <th>结果说明</th>
                </tr>
              </thead>
              <tbody>
                {log.data.batches.results.map((b) => (
                  <tr key={b.id}>
                    <td>
                      {new Date(b.created_at + "Z").toLocaleString("zh-CN")}
                    </td>
                    <td>{b.recipient}</td>
                    <td>
                      <Badge status={b.status} />
                    </td>
                    <td>{b.attempts_total}</td>
                    <td>{b.error_code || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager
          page={page}
          total={log.data?.batches.count || 0}
          onChange={setPage}
        />
      </section>
      <section className="panel">
        <div className="panel-title">
          <h2>任务运行记录</h2>
        </div>
        {!log.data?.runs.results.length ? (
          <Empty message="任务尚未执行" />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>扫描时间</th>
                  <th>状态</th>
                  <th>新增提醒</th>
                  <th>已发送</th>
                  <th>失败 / 待核实</th>
                </tr>
              </thead>
              <tbody>
                {log.data.runs.results.map((r) => (
                  <tr key={r.id}>
                    <td>
                      {new Date(r.started_at + "Z").toLocaleString("zh-CN")}
                    </td>
                    <td>
                      <Badge status={r.status} />
                    </td>
                    <td>{r.counts.generated || 0}</td>
                    <td>{r.counts.sent || 0}</td>
                    <td>
                      {(r.counts.failed || 0) + (r.counts.uncertain || 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
