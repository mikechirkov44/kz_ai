import type { ReactNode } from "react";

type IconProps = { size?: number };

export default function ExcelIcon({ size = 16 }: IconProps) {
  return (
    <svg className="btn-icon excel-icon" width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M11.1 3.15h5.7L21 7.5v12.1c0 .9-.75 1.65-1.65 1.65h-8.25c-.9 0-1.65-.75-1.65-1.65V4.8c0-.9.75-1.65 1.65-1.65Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
      <path d="M16.8 3.25v4.25H21" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" />
      <rect x="2.25" y="8.2" width="12.7" height="12.7" rx="1.7" fill="#217346" />
      <rect x="3.95" y="9.9" width="9.3" height="9.3" rx=".55" fill="#fff" />
      <path
        d="M6.15 11.35h1.7L8.6 13.7l.75-2.35h1.7L9.7 14.3l1.55 3.35H9.45L8.6 15.1l-.85 2.55H6.05l1.55-3.35-1.45-2.95Z"
        fill="#217346"
      />
    </svg>
  );
}

export function ExcelLabel({ children, size = 16 }: { children: ReactNode; size?: number }) {
  return (
    <>
      <ExcelIcon size={size} />
      {children}
    </>
  );
}
