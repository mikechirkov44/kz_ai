const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type Tokens = { access_token: string; refresh_token: string; expires_in: number };

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  const auth = authHeaders();
  Object.entries(auth).forEach(([k, v]) => headers.set(k, v as string));
  if (!(init.body instanceof FormData) && !headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function login(email: string, password: string): Promise<Tokens> {
  return api<Tokens>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function gradeClass(grade: string): string {
  if (grade.includes("Доп") || grade.includes("от 500") || grade.includes("350")) return "grade-high";
  if (grade.includes("200") || grade.includes("100–200")) return "grade-mid";
  return "grade-low";
}
