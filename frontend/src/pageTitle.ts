export const APP_TITLE = "AI Jewelry";

export function formatPageTitle(title: string): string {
  const name = title.trim();
  return name ? `${name} · ${APP_TITLE}` : APP_TITLE;
}
