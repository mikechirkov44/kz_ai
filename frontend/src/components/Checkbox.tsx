import type { CSSProperties, MouseEventHandler, ReactNode } from "react";

type Props = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
  title?: string;
  "aria-label"?: string;
  onClick?: MouseEventHandler<HTMLLabelElement>;
};

export default function Checkbox({
  checked,
  onChange,
  disabled = false,
  children,
  className,
  style,
  title,
  "aria-label": ariaLabel,
  onClick,
}: Props) {
  const classes = [
    "ui-check",
    checked ? "is-on" : "",
    disabled ? "is-disabled" : "",
    children ? "" : "is-bare",
    className || "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <label className={classes} style={style} title={title} onClick={onClick}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => {
          if (disabled) return;
          onChange(e.target.checked);
        }}
        aria-label={ariaLabel}
      />
      <span className="ui-check-box" aria-hidden>
        <svg className="ui-check-mark" viewBox="0 0 16 16">
          <path
            d="M3.2 8.2 6.4 11.4 12.8 4.4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      {children ? <span className="ui-check-text">{children}</span> : null}
    </label>
  );
}
