import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api";
import BrandLogo from "../components/BrandLogo";

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("admin12345");
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
      navigate("/");
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
          Акции
          <br />
          по клиентам
        </h1>
        <p>
          Единый контур аналитики акций ювелирного холдинга: мотивация, оборачиваемость, план/факт и
          рекомендации на данных 1С.
        </p>
      </section>
      <form className="login-card" onSubmit={onSubmit}>
        <div className="login-card-brand">
          <BrandLogo size={40} />
        </div>
        <h1>Вход</h1>
        <p className="muted" style={{ marginTop: 0 }}>
          Рабочее пространство аналитики
        </p>
        {error && <div className="alert">{error}</div>}
        <label className="field" style={{ marginBottom: 12 }}>
          <span>Email</span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </label>
        <label className="field" style={{ marginBottom: 18 }}>
          <span>Пароль</span>
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
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
