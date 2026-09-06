export const THEME_KEY = "kz_ai_theme";

export const THEME_IDS = ["emerald", "amber", "indigo", "dark"] as const;

export type ThemeId = (typeof THEME_IDS)[number];

export type ThemeOption = {
  id: ThemeId;
  title: string;
  hint: string;
  swatches: [string, string, string];
};

export const THEMES: ThemeOption[] = [
  { id: "emerald", title: "Изумруд", hint: "Светлая бирюза", swatches: ["#eef2f6", "#0d9488", "#111827"] },
  { id: "amber", title: "Янтарь", hint: "Тёплый золотой", swatches: ["#f7f1e8", "#b45309", "#1c1917"] },
  { id: "indigo", title: "Индиго", hint: "Холодный синий", swatches: ["#eef0f7", "#4f46e5", "#111827"] },
  { id: "dark", title: "Тёмная", hint: "Тёмный фон", swatches: ["#0f141a", "#2dd4bf", "#e5e7eb"] },
];

export function isThemeId(value: string | null | undefined): value is ThemeId {
  return THEME_IDS.includes(value as ThemeId);
}

export function readTheme(): ThemeId {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (isThemeId(stored)) return stored;
  } catch {
    /* private mode */
  }
  return "emerald";
}

export function applyTheme(id: ThemeId): ThemeId {
  const next = isThemeId(id) ? id : "emerald";
  document.documentElement.setAttribute("data-theme", next);
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {
    /* ignore */
  }
  return next;
}
