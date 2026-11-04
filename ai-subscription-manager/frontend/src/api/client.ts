import type { Page } from "./types";
let csrf = "";
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields: Record<string, string> = {},
  ) {
    super(message);
  }
}
export async function refreshCsrf() {
  const r = await fetch("/api/auth/csrf/", { credentials: "same-origin" });
  if (!r.ok) throw new Error("无法连接后台");
  csrf = (await r.json()).csrfToken;
}
export async function request<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const write = !!init.method && !["GET", "HEAD"].includes(init.method);
  if (write && !csrf) await refreshCsrf();
  const r = await fetch("/api" + path, {
    ...init,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(write ? { "X-CSRFToken": csrf } : {}),
      ...init.headers,
    },
  });
  if (r.status === 204) return undefined as T;
  const data = await r.json();
  if (!r.ok) {
    if (r.status === 403 && data.code === "csrf" && retry) {
      await refreshCsrf();
      return request(path, init, false);
    }
    if (r.status === 401 && path !== "/auth/me/")
      window.dispatchEvent(new Event("auth-expired"));
    throw new ApiError(
      r.status,
      data.code,
      data.message || "请求失败",
      data.fields,
    );
  }
  if (data.csrfToken) csrf = data.csrfToken;
  return data as T;
}
export const mutate = <T>(path: string, data: unknown, method = "POST") =>
  request<T>(path, { method, body: JSON.stringify(data) });
export async function all<T>(path: string): Promise<T[]> {
  let page = 1;
  const rows: T[] = [];
  while (true) {
    const r = await request<Page<T>>(
      `${path}${path.includes("?") ? "&" : "?"}page=${page}`,
    );
    rows.push(...r.results);
    if (!r.next) return rows;
    page = r.next;
  }
}
