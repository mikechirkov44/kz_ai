import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import BrandLogo from "./components/BrandLogo";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import MotivationPage from "./pages/MotivationPage";
import TurnoverPage from "./pages/TurnoverPage";
import QuarterlyPage from "./pages/QuarterlyPage";
import RecommendationsPage from "./pages/RecommendationsPage";
import FactShipmentsPage from "./pages/FactShipmentsPage";
import NomenclaturePage from "./pages/NomenclaturePage";
import CounterpartiesCatalogPage from "./pages/CounterpartiesCatalogPage";
import DocumentsPage from "./pages/DocumentsPage";
import AdminPage from "./pages/AdminPage";
import HelpPage from "./pages/HelpPage";

const SIDEBAR_KEY = "sidebar_collapsed";

type NavItem = { to: string; label: string; short: string; end?: boolean };

const ANALYTICS: NavItem[] = [
  { to: "/", label: "Дашборд", short: "Дб", end: true },
  { to: "/motivation", label: "Мотивация", short: "Мт" },
  { to: "/turnover", label: "Оборачиваемость", short: "Об" },
  { to: "/quarterly", label: "Квартальные планы", short: "Кв" },
  { to: "/fact", label: "Факт отгрузок", short: "Фк" },
  { to: "/recommendations", label: "Рекомендации", short: "Рк" },
];

const ONES: NavItem[] = [
  { to: "/nomenclature", label: "Номенклатура", short: "Нм" },
  { to: "/counterparties", label: "Контрагенты", short: "Кт" },
  { to: "/documents", label: "Журнал документов", short: "Жд" },
];

const DATA: NavItem[] = [
  { to: "/uploads", label: "Загрузка Excel", short: "Ex" },
  { to: "/admin", label: "Админ", short: "Ад" },
  { to: "/help", label: "Справка", short: "?" },
];

function NavGroup({
  title,
  items,
  collapsed,
}: {
  title: string;
  items: NavItem[];
  collapsed: boolean;
}) {
  return (
    <>
      <div className="nav-section" title={title}>
        {collapsed ? "·" : title}
      </div>
      <nav className="nav">
        {items.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} title={item.label}>
            <span className="nav-short" aria-hidden>
              {item.short}
            </span>
            <span className="nav-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_KEY) === "1");

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    navigate("/login");
  };

  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="brand" title="Акции по клиентам">
            <BrandLogo size={collapsed ? 34 : 40} />
            {!collapsed && (
              <div className="brand-text">
                Акции
                <br />
                по клиентам
                <span>Analytics · Jewelry</span>
              </div>
            )}
          </div>
          <button
            type="button"
            className="sidebar-toggle"
            onClick={() => setCollapsed((v) => !v)}
            title={collapsed ? "Развернуть меню" : "Свернуть меню"}
            aria-label={collapsed ? "Развернуть меню" : "Свернуть меню"}
          >
            {collapsed ? "›" : "‹"}
          </button>
        </div>
        <NavGroup title="Аналитика" items={ANALYTICS} collapsed={collapsed} />
        <NavGroup title="1С" items={ONES} collapsed={collapsed} />
        <NavGroup title="Данные" items={DATA} collapsed={collapsed} />
        <div className="sidebar-foot">
          <button
            className="btn ghost"
            style={{ width: "100%" }}
            onClick={logout}
            title="Выйти"
          >
            {collapsed ? "⎋" : "Выйти"}
          </button>
        </div>
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
      <Route path="/fact" element={<Private><FactShipmentsPage /></Private>} />
      <Route path="/recommendations" element={<Private><RecommendationsPage /></Private>} />
      <Route path="/nomenclature" element={<Private><NomenclaturePage /></Private>} />
      <Route path="/counterparties" element={<Private><CounterpartiesCatalogPage /></Private>} />
      <Route path="/documents" element={<Private><DocumentsPage /></Private>} />
      <Route path="/admin" element={<Private><AdminPage /></Private>} />
      <Route path="/help" element={<Private><HelpPage /></Private>} />
    </Routes>
  );
}
