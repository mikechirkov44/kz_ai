export function userInitials(label: string): string {
  const source = label.trim();
  if (!source) return "?";
  const local = source.includes("@") ? source.slice(0, source.indexOf("@")) : source;
  const parts = local.split(/[\s._-]+/).filter(Boolean);
  if (!parts.length) return "?";
  const letters =
    parts.length === 1 ? parts[0].slice(0, 2) : `${parts[0][0]}${parts[parts.length - 1][0]}`;
  return letters.toUpperCase();
}
