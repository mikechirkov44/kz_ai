import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { changePassword } from "../api";
import { useAuth } from "../auth";
import BrandLogo from "../components/BrandLogo";
import PageHeader from "../components/PageHeader";

export default function ChangePasswordPage() {
  const navigate = useNavigate();
  const { me, refreshMe } = useAuth();
  const forced = Boolean(me?.must_change_password);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (newPassword !== confirm) {
      setError("Пароли не совпадают");
      return;
    }
    if (newPassword.length < 8) {
      setError("Минимум 8 символов");
      return;
    }
    setLoading(true);
    try {
      await changePassword(currentPassword, newPassword);
      await refreshMe();
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка смены пароля");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel" style={{ maxWidth: 480, margin: "40px auto" }}>
      <PageHeader
        title="Смена пароля"
        subtitle={forced ? "Пароль устарел — нужно задать новый (раз в 90 дней)" : "Обновите пароль учётной записи"}
      />
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
        <BrandLogo size={40} />
      </div>
      {error && <div className="alert">{error}</div>}
      <form onSubmit={onSubmit}>
        <label className="field" style={{ marginBottom: 12 }}>
          <span>Текущий пароль</span>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        <label className="field" style={{ marginBottom: 12 }}>
          <span>Новый пароль</span>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
        </label>
        <label className="field" style={{ marginBottom: 18 }}>
          <span>Повтор нового пароля</span>
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
        </label>
        <button className="btn" type="submit" disabled={loading} style={{ width: "100%" }}>
          {loading ? "Сохраняем…" : "Сохранить"}
        </button>
      </form>
    </div>
  );
}
