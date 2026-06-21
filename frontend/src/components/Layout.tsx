import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { cn } from "../lib/utils";

const NAV = [
  { to: "/dashboard", label: "Command Center", icon: "⚡" },
  { to: "/events", label: "Events", icon: "📋" },
  { to: "/events/new", label: "Create Event", icon: "➕", roles: ["admin", "traffic_officer"] },
  { to: "/analytics", label: "Analytics", icon: "📊" },
  { to: "/advisories", label: "Public Advisories", icon: "📢" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => { logout(); navigate("/login"); };

  const visibleNav = NAV.filter(n => !n.roles || n.roles.includes(user?.role ?? ""));

  return (
    <div className="flex min-h-screen bg-bg grid-bg">
      {/* Sidebar */}
      <aside className="w-64 bg-surface border-r border-border flex flex-col fixed h-full z-20">
        {/* Logo */}
        <div className="p-5 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-accent/20 border border-accent/40 rounded-lg flex items-center justify-center text-lg">
              ⚡
            </div>
            <div>
              <p className="font-bold text-white leading-tight">EventFlow AI</p>
              <p className="text-[10px] text-muted uppercase tracking-wider">Traffic Command</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {visibleNav.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-accent/15 text-accent border border-accent/25"
                  : "text-muted hover:text-white hover:bg-white/5"
              )}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* User info + logout */}
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 bg-accent/20 rounded-full flex items-center justify-center text-accent font-bold text-sm">
              {user?.full_name?.[0] ?? "U"}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-white truncate">{user?.full_name}</p>
              <p className="text-[11px] text-muted capitalize">{user?.role?.replace("_", " ")}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="btn-ghost w-full text-sm text-left px-3 py-2">
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 ml-64 min-h-screen">
        <div className="p-6 animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
