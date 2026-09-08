import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api";
import BrandLogo from "../components/BrandLogo";

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const tokens = await login(email, password);
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
      navigate(tokens.must_change_password ? "/change-password" : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <section className="login-hero">
        <BrandLogo size={56} />
        <h1 className="brand-mark">
          AI Jewelry
          <br />
          Analytics
        </h1>
        <p>
          Мотивация, оборачиваемость, план/факт и рекомендации на данных 1С.
        </p>
      </section>
      <form className="login-card" onSubmit={onSubmit}>
        <div className="login-card-brand">
          <BrandLogo size={40} />
        </div>
        <h1>Вход</h1>
        <p className="muted" style={{ marginTop: 0 }}>
          Аналитика акций по клиентам
        </p>
        {error && <div className="alert">{error}</div>}
        <label className="field" style={{ marginBottom: 12 }}>
          <span>Email</span>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            autoComplete="username"
            required
          />
        </label>
        <label className="field" style={{ marginBottom: 18 }}>
          <span>Пароль</span>
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            autoComplete="current-password"
            required
          />
        </label>
        <button className="btn" type="submit" disabled={loading} style={{ width: "100%" }}>
          {loading ? "Входим…" : "Войти"}
        </button>
      </form>
    </div>
  );
}
