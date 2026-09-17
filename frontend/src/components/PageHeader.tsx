import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { ROLE_LABELS } from "../api";
import { useAuth } from "../auth";
import { usePageTitle } from "../usePageTitle";
import AssistantLaunch from "./AssistantLaunch";
import HeaderAccount from "./HeaderAccount";
import NavIcon, { iconForPath, type NavIconName } from "./NavIcon";

type Props = {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  icon?: NavIconName;
  chrome?: boolean;
};

export default function PageHeader({ title, subtitle, actions, icon, chrome = true }: Props) {
  const { pathname } = useLocation();
  const { me } = useAuth();
  const name = icon ?? iconForPath(pathname);
  usePageTitle(title);

  return (
    <header className="page-header">
      <div className="page-header-lead">
        {name ? (
          <Link to="/" className="page-header-icon" title="На главную" aria-label="На главную">
            <NavIcon name={name} size={22} />
          </Link>
        ) : null}
        <div>
          <h1>{title}</h1>
          {subtitle ? <p className="muted">{subtitle}</p> : null}
        </div>
      </div>
      {actions || chrome ? (
        <div className="page-header-end">
          {actions ? <div className="toolbar">{actions}</div> : null}
          {chrome ? (
            <div className="header-tools">
              <AssistantLaunch />
              {me ? (
                <HeaderAccount
                  name={me.full_name || me.email}
                  email={me.email}
                  roleLabel={ROLE_LABELS[me.role] || me.role}
                />
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </header>
  );
}
