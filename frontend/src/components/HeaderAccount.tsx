import { useNavigate } from "react-router-dom";
import { clearSession } from "../api";
import { userInitials } from "../userInitials";
import NavIcon from "./NavIcon";

type Props = {
  name: string;
  email: string;
  roleLabel: string;
};

export default function HeaderAccount({ name, email, roleLabel }: Props) {
  const navigate = useNavigate();

  return (
    <div className="header-account">
      <div className="header-account-avatar" aria-hidden>
        {userInitials(name)}
      </div>
      <div className="header-account-meta" title={email}>
        <strong>{name}</strong>
        <span>{roleLabel}</span>
      </div>
      <div className="header-account-actions">
        <button
          type="button"
          className="header-icon-btn"
          title="Сменить пароль"
          aria-label="Сменить пароль"
          onClick={() => navigate("/change-password")}
        >
          <NavIcon name="lock" size={16} />
        </button>
        <button
          type="button"
          className="header-icon-btn"
          title="Выйти"
          aria-label="Выйти"
          onClick={() => {
            clearSession();
            navigate("/login");
          }}
        >
          <NavIcon name="logout" size={16} />
        </button>
      </div>
    </div>
  );
}
