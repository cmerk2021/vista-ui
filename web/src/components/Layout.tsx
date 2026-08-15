import { NavLink } from "react-router-dom";
import { Home, LayoutGrid, Hash, ScrollText, Settings } from "lucide-react";
import { useStore } from "../lib/store";

const NAV = [
  { to: "/", label: "Dashboard", icon: Home, end: true },
  { to: "/zones", label: "Zones", icon: LayoutGrid, end: false },
  { to: "/keypad", label: "Keypad", icon: Hash, end: false },
  { to: "/log", label: "Log", icon: ScrollText, end: false },
  { to: "/settings", label: "Settings", icon: Settings, end: false },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const wsConnected = useStore((s) => s.wsConnected);
  const panel = useStore((s) => s.panel);
  const online = wsConnected && (panel?.logged_in ?? false);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <img src="/favicon.svg" className="brand-logo" alt="" />
          <span>
            VISTA <small>tpi</small>
          </span>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <span className="mono dim" style={{ fontSize: 11 }}>
            {online ? "PANEL LINK" : wsConnected ? "NO PANEL" : "OFFLINE"}
          </span>
          <span className={`conn-dot ${online ? "online" : "offline"}`} />
        </div>
      </header>
      <main className="page">{children}</main>
      <nav className="nav">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <Icon size={20} />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
