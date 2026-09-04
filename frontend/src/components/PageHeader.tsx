import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import NavIcon, { iconForPath, type NavIconName } from "./NavIcon";

type Props = {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  icon?: NavIconName;
};

export default function PageHeader({ title, subtitle, actions, icon }: Props) {
  const { pathname } = useLocation();
  const name = icon ?? iconForPath(pathname);

  return (
    <header className="page-header">
      <div className="page-header-lead">
        {name ? (
          <span className="page-header-icon">
            <NavIcon name={name} size={22} />
          </span>
        ) : null}
        <div>
          <h1>{title}</h1>
          {subtitle ? <p className="muted">{subtitle}</p> : null}
        </div>
      </div>
      {actions ? <div className="toolbar">{actions}</div> : null}
    </header>
  );
}
