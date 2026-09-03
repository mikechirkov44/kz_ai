import type { ReactNode } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import MotivationPage from "./pages/MotivationPage";
import TurnoverPage from "./pages/TurnoverPage";
import QuarterlyPage from "./pages/QuarterlyPage";
import RecommendationsPage from "./pages/RecommendationsPage";
import AdminPage from "./pages/AdminPage";

function Shell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    navigate("/login");
  };
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">Акции<br />по клиентам</div>
        <nav className="nav">
          <NavLink to="/" end>Дашборд</NavLink>
          <NavLink to="/uploads">Загрузка Excel</NavLink>
          <NavLink to="/motivation">Мотивация</NavLink>
          <NavLink to="/turnover">Оборачиваемость</NavLink>
          <NavLink to="/quarterly">Квартальные планы</NavLink>
          <NavLink to="/recommendations">AI-рекомендации</NavLink>
          <NavLink to="/admin">Админ</NavLink>
        </nav>
        <button className="btn secondary" style={{ marginTop: 24, color: "#fff", borderColor: "rgba(255,255,255,.35)" }} onClick={logout}>
          Выйти
        </button>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}

function Private({ children }: { children: ReactNode }) {
  const token = localStorage.getItem("access_token");
  if (!token) return <Navigate to="/login" replace />;
  return <Shell>{children}</Shell>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Private><DashboardPage /></Private>} />
      <Route path="/uploads" element={<Private><UploadPage /></Private>} />
      <Route path="/motivation" element={<Private><MotivationPage /></Private>} />
      <Route path="/turnover" element={<Private><TurnoverPage /></Private>} />
      <Route path="/quarterly" element={<Private><QuarterlyPage /></Private>} />
      <Route path="/recommendations" element={<Private><RecommendationsPage /></Private>} />
      <Route path="/admin" element={<Private><AdminPage /></Private>} />
    </Routes>
  );
}
