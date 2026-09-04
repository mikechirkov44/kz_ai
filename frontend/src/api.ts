const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type Tokens = { access_token: string; refresh_token: string; expires_in: number };

export type Counterparty = {
  id: string;
  name: string;
  source_id: string;
  is_promo: boolean;
  work_type?: string | null;
  work_type_percent?: number;
  shops?: string[];
  manager_id?: string | null;
  manager_name?: string | null;
};

export type Me = {
  id: string;
  email: string;
  role: string;
  region?: string | null;
  full_name?: string | null;
  active: boolean;
};

export const ROLE_LABELS: Record<string, string> = {
  admin: "Админ",
  regional_director: "Рег. директор",
  manager: "Менеджер",
  analytic: "Аналитик",
};

export function canSeeAdmin(role?: string | null): boolean {
  return role === "admin";
}

export function canAssignManagers(role?: string | null): boolean {
  return role === "admin" || role === "regional_director";
}

let refreshPromise: Promise<boolean> | null = null;

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function clearSession() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

function redirectToLogin() {
  clearSession();
  if (!window.location.pathname.startsWith("/login")) {
    window.location.assign("/login");
  }
}

function parseError(text: string, status: number): string {
  try {
    const json = JSON.parse(text) as { detail?: unknown };
    const detail = json.detail;
    if (typeof detail === "string") {
      if (detail === "Invalid token" || detail === "Not authenticated" || detail === "User inactive") {
        return "Сессия истекла — войдите снова";
      }
      if (detail === "Account locked") return "Аккаунт временно заблокирован";
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail.map((d) => (typeof d === "object" && d && "msg" in d ? String(d.msg) : String(d))).join("; ");
    }
  } catch {
    /* plain text */
  }
  if (status === 401) return "Сессия истекла — войдите снова";
  if (status === 429) return "Слишком много запросов, подождите минуту";
  return text || `Ошибка ${status}`;
}

async function tryRefresh(): Promise<boolean> {
  const refresh = localStorage.getItem("refresh_token");
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const tokens = (await res.json()) as Tokens;
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    return true;
  } catch {
    return false;
  }
}

async function refreshOnce(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = tryRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

async function request(path: string, init: RequestInit = {}, retried = false): Promise<Response> {
  const headers = new Headers(init.headers || {});
  const auth = authHeaders();
  Object.entries(auth).forEach(([k, v]) => headers.set(k, v as string));
  if (!(init.body instanceof FormData) && !headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (res.status !== 401 || path.startsWith("/api/v1/auth/login") || path.startsWith("/api/v1/auth/refresh")) {
    return res;
  }
  if (retried) {
    redirectToLogin();
    return res;
  }
  const ok = await refreshOnce();
  if (!ok) {
    redirectToLogin();
    return res;
  }
  return request(path, init, true);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await request(path, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(parseError(text, res.status));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** Download binary (xlsx) with auth. */
export async function downloadFile(path: string, fallbackName = "export.xlsx"): Promise<void> {
  const res = await request(path);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(parseError(text, res.status));
  }
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  const filename = match?.[1] || fallbackName;
  const blob = await res.blob();
  if (blob.size < 4) throw new Error("Пустой файл");
  const head = new Uint8Array(await blob.slice(0, 2).arrayBuffer());
  if (filename.endsWith(".xlsx") && !(head[0] === 0x50 && head[1] === 0x4b)) {
    throw new Error("Сервер вернул не Excel-файл — войдите снова и повторите");
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function login(email: string, password: string): Promise<Tokens> {
  return api<Tokens>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function listCounterparties(params: {
  promo_only?: boolean;
  source_id?: string;
  q?: string;
} = {}): Promise<Counterparty[]> {
  const sp = new URLSearchParams();
  if (params.promo_only) sp.set("promo_only", "true");
  if (params.source_id) sp.set("source_id", params.source_id);
  if (params.q) sp.set("q", params.q);
  const qs = sp.toString();
  return api<Counterparty[]>(`/api/v1/counterparties${qs ? `?${qs}` : ""}`);
}

export function formatMoney(value: number | string | null | undefined): string {
  const n = Number(value ?? 0);
  return n.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

export function gradeClass(grade: string): string {
  if (grade.includes("Доп") || grade.includes("от 500") || grade.includes("350")) return "grade-high";
  if (grade.includes("200") || grade.includes("100–200") || grade.includes("100-200")) return "grade-mid";
  return "grade-low";
}

export { API_URL };
