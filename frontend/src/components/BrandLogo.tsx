import { useId } from "react";

type Props = { size?: number; className?: string };

/** Знак бренда: грань камня + кольцо */
export default function BrandLogo({ size = 36, className = "" }: Props) {
  const uid = useId().replace(/:/g, "");
  const gradId = `logoBg-${uid}`;

  return (
    <svg
      className={`brand-logo ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <rect width="40" height="40" rx="10" fill={`url(#${gradId})`} />
      <circle cx="20" cy="20" r="11.5" stroke="rgba(255,255,255,0.35)" strokeWidth="1.5" />
      <path
        d="M20 9.5L28.5 20L20 30.5L11.5 20L20 9.5Z"
        fill="rgba(255,255,255,0.95)"
        stroke="rgba(255,255,255,0.2)"
        strokeWidth="0.5"
      />
      <path d="M20 14L24.2 20L20 26L15.8 20L20 14Z" fill="#0f766e" opacity="0.9" />
      <defs>
        <linearGradient id={gradId} x1="6" y1="4" x2="36" y2="38" gradientUnits="userSpaceOnUse">
          <stop stopColor="#14b8a6" />
          <stop offset="1" stopColor="#0f766e" />
        </linearGradient>
      </defs>
    </svg>
  );
}
