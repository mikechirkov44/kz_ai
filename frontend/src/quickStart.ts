import { canSeeAdmin } from "./api";

export const QUICK_START_MAX = 6;
export const QUICK_START_KEY_PREFIX = "kz_ai_quick_start_";

export type QuickStartTool = {
  to: string;
  label: string;
  adminOnly?: boolean;
};

export const QUICK_START_TOOLS: QuickStartTool[] = [
  { to: "/uploads", label: "Ввод данных" },
  { to: "/quarterly", label: "Квартальные отчеты" },
  { to: "/motivation", label: "Мотивация" },
  { to: "/turnover", label: "Оборачиваемость" },
  { to: "/fact", label: "Факт отгрузок" },
  { to: "/recommendations", label: "Рекомендации" },
  { to: "/nomenclature", label: "Номенклатура" },
  { to: "/counterparties", label: "Контрагенты" },
  { to: "/documents", label: "Журнал документов" },
  { to: "/users", label: "Пользователи", adminOnly: true },
  { to: "/audit", label: "Аудит", adminOnly: true },
  { to: "/admin", label: "Администрирование", adminOnly: true },
];

const DEFAULTS: Record<string, string[]> = {
  manager: ["/uploads", "/quarterly", "/motivation", "/recommendations"],
  analytic: ["/quarterly", "/turnover", "/fact", "/recommendations"],
  regional_director: ["/quarterly", "/turnover", "/fact", "/recommendations"],
  admin: ["/admin", "/users", "/uploads", "/quarterly"],
};

export function allowedQuickStartTools(role?: string | null): QuickStartTool[] {
  const admin = canSeeAdmin(role);
  return QUICK_START_TOOLS.filter((tool) => !tool.adminOnly || admin);
}

export function defaultQuickStartPaths(role?: string | null): string[] {
  const allowed = new Set(allowedQuickStartTools(role).map((tool) => tool.to));
  const preset = DEFAULTS[role || ""] || ["/quarterly", "/motivation", "/turnover", "/documents"];
  return preset.filter((path) => allowed.has(path)).slice(0, QUICK_START_MAX);
}

export function sanitizeQuickStartPaths(paths: string[], role?: string | null): string[] {
  const allowed = new Set(allowedQuickStartTools(role).map((tool) => tool.to));
  const seen = new Set<string>();
  const out: string[] = [];
  for (const path of paths) {
    if (!allowed.has(path) || seen.has(path)) continue;
    seen.add(path);
    out.push(path);
    if (out.length >= QUICK_START_MAX) break;
  }
  return out.length ? out : defaultQuickStartPaths(role);
}

export function storageKeyForUser(userId: string): string {
  return `${QUICK_START_KEY_PREFIX}${userId}`;
}

export function readQuickStartPaths(userId: string, role?: string | null): string[] {
  try {
    const raw = localStorage.getItem(storageKeyForUser(userId));
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.every((item) => typeof item === "string")) {
        return sanitizeQuickStartPaths(parsed, role);
      }
    }
  } catch {
    /* private mode or bad json */
  }
  return defaultQuickStartPaths(role);
}

export function writeQuickStartPaths(userId: string, paths: string[], role?: string | null): string[] {
  const next = sanitizeQuickStartPaths(paths, role);
  try {
    localStorage.setItem(storageKeyForUser(userId), JSON.stringify(next));
  } catch {
    /* private mode */
  }
  return next;
}

export function resolveQuickStartTools(paths: string[], role?: string | null): QuickStartTool[] {
  const byPath = new Map(allowedQuickStartTools(role).map((tool) => [tool.to, tool]));
  return sanitizeQuickStartPaths(paths, role)
    .map((path) => byPath.get(path))
    .filter((tool): tool is QuickStartTool => Boolean(tool));
}
