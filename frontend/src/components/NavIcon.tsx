export type NavIconName =
  | "dashboard"
  | "star"
  | "cycle"
  | "calendar"
  | "box"
  | "bulb"
  | "gem"
  | "users"
  | "document"
  | "upload"
  | "user"
  | "clipboard"
  | "gear"
  | "help";

export const NAV_ICON_BY_PATH: { path: string; end?: boolean; icon: NavIconName }[] = [
  { path: "/", end: true, icon: "dashboard" },
  { path: "/motivation", icon: "star" },
  { path: "/turnover", icon: "cycle" },
  { path: "/quarterly", icon: "calendar" },
  { path: "/fact", icon: "box" },
  { path: "/recommendations", icon: "bulb" },
  { path: "/nomenclature", icon: "gem" },
  { path: "/counterparties", icon: "users" },
  { path: "/documents", icon: "document" },
  { path: "/uploads", icon: "upload" },
  { path: "/users", icon: "user" },
  { path: "/audit", icon: "clipboard" },
  { path: "/admin", icon: "gear" },
  { path: "/help", icon: "help" },
];

export function iconForPath(pathname: string): NavIconName | undefined {
  const exact = NAV_ICON_BY_PATH.find((row) => row.end && pathname === row.path);
  if (exact) return exact.icon;
  const hit = NAV_ICON_BY_PATH.filter((row) => !row.end && pathname.startsWith(row.path)).sort(
    (a, b) => b.path.length - a.path.length,
  )[0];
  return hit?.icon;
}

type Props = { name: NavIconName; size?: number; className?: string };

export default function NavIcon({ name, size = 20, className = "" }: Props) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {paths(name)}
    </svg>
  );
}

function paths(name: NavIconName) {
  switch (name) {
    case "dashboard":
      return (
        <>
          <rect x="3.5" y="3.5" width="7.5" height="7.5" rx="1.5" />
          <rect x="13" y="3.5" width="7.5" height="4.5" rx="1.5" />
          <rect x="13" y="10.5" width="7.5" height="10" rx="1.5" />
          <rect x="3.5" y="13.5" width="7.5" height="7" rx="1.5" />
        </>
      );
    case "star":
      return (
        <path d="M12 3.6l2.2 4.6 5 .7-3.6 3.5.9 5.1L12 15.2 7.5 17.5l.9-5.1L4.8 8.9l5-.7L12 3.6z" />
      );
    case "cycle":
      return (
        <>
          <path d="M4.5 12a7.5 7.5 0 0 1 12.4-5.7L19 8" />
          <path d="M19.5 4.5v4h-4" />
          <path d="M19.5 12a7.5 7.5 0 0 1-12.4 5.7L5 16" />
          <path d="M4.5 19.5v-4h4" />
        </>
      );
    case "calendar":
      return (
        <>
          <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
          <path d="M3.5 10h17M8 3.5V7M16 3.5V7" />
        </>
      );
    case "box":
      return (
        <>
          <path d="M3.8 7.5 12 3.5l8.2 4L12 11.5 3.8 7.5z" />
          <path d="M3.8 7.5V16L12 20.5 20.2 16V7.5" />
          <path d="M12 11.5V20.5" />
        </>
      );
    case "bulb":
      return (
        <>
          <path d="M9 18h6M10 21h4" />
          <path d="M8 14.2A5.5 5.5 0 1 1 16 14.2c-.8.9-1.5 1.8-1.5 3.3h-5c0-1.5-.7-2.4-1.5-3.3z" />
        </>
      );
    case "gem":
      return <path d="M12 3.5 20 10.5 12 20.5 4 10.5 12 3.5zM4 10.5h16M9.2 6.2 12 10.5l2.8-4.3" />;
    case "users":
      return (
        <>
          <circle cx="9" cy="8" r="2.6" />
          <path d="M3.8 18.5c.4-3 2.4-4.6 5.2-4.6s4.8 1.6 5.2 4.6" />
          <circle cx="16.4" cy="8.4" r="2.2" />
          <path d="M15.2 13.9c2.2.2 3.8 1.6 4.2 4.1" />
        </>
      );
    case "document":
      return (
        <>
          <path d="M7 3.5h7l5 5V20a1.5 1.5 0 0 1-1.5 1.5H7A1.5 1.5 0 0 1 5.5 20V5A1.5 1.5 0 0 1 7 3.5z" />
          <path d="M14 3.5V9h5.5M8.5 13h7M8.5 16.5h5" />
        </>
      );
    case "upload":
      return (
        <>
          <path d="M12 15.5V6.5M8.5 10 12 6.5 15.5 10" />
          <path d="M5 16.5V19a1.5 1.5 0 0 0 1.5 1.5h11A1.5 1.5 0 0 0 19 19v-2.5" />
        </>
      );
    case "user":
      return (
        <>
          <circle cx="12" cy="8" r="3" />
          <path d="M5 19.5c.6-3.6 3-5.5 7-5.5s6.4 1.9 7 5.5" />
        </>
      );
    case "clipboard":
      return (
        <>
          <rect x="6" y="4.5" width="12" height="16" rx="2" />
          <path d="M9 4.5h6v2.6H9zM8.5 11h7M8.5 14.5h5" />
        </>
      );
    case "gear":
      return (
        <>
          <circle cx="12" cy="12" r="3" />
          <path d="M12 4.2v2.2M12 17.6v2.2M4.2 12h2.2M17.6 12h2.2M6.4 6.4l1.6 1.6M16 16l1.6 1.6M17.6 6.4 16 8M8 16l-1.6 1.6" />
        </>
      );
    case "help":
      return (
        <>
          <circle cx="12" cy="12" r="8.5" />
          <path d="M9.6 9.4a2.4 2.4 0 1 1 3.5 2.1c-.7.4-1.1.9-1.1 1.8V14" />
          <path d="M12 17.2h.01" />
        </>
      );
  }
}
