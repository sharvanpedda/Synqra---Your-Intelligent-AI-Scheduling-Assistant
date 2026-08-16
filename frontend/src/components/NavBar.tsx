import { NavLink } from "react-router-dom";
import { useAuth } from "../lib/auth";
import Brand from "./Brand";

export default function NavBar() {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-ink/70 backdrop-blur-xl">
      <nav className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-8">
          <NavLink to="/dashboard" aria-label="Dashboard">
            <Brand size="lg" />
          </NavLink>
          <div className="hidden items-center gap-2 sm:flex">
            <NavPill to="/dashboard">Dashboard</NavPill>
            <NavPill to="/schedules">My Schedules</NavPill>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* agent status */}
          <div className="hidden items-center gap-1.5 rounded-full border border-line bg-panel px-3 py-1.5 font-mono text-[11px] text-mist md:flex">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping2 rounded-full bg-free" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-free" />
            </span>
            AGENT ONLINE
          </div>

          {user && (
            <div className="hidden items-center gap-2 text-xs text-mist sm:flex">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-signal to-free font-display text-[11px] font-semibold text-ink">
                {(user.display_name || user.email || "?").charAt(0).toUpperCase()}
              </span>
              <span className="max-w-[140px] truncate">{user.display_name || user.email}</span>
            </div>
          )}

          <button
            onClick={() => logout()}
            className="rounded-lg border border-line px-3 py-1.5 text-xs text-mist transition-colors hover:border-alert/50 hover:text-alert"
          >
            Sign out
          </button>
        </div>
      </nav>
    </header>
  );
}

function NavPill({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `rounded-lg px-3 py-1.5 text-sm transition-colors ${
          isActive
            ? "bg-panel text-busy shadow-[0_1px_0_0_rgba(242,166,90,0.35)_inset]"
            : "text-mist hover:bg-panel/60 hover:text-busy"
        }`
      }
    >
      {children}
    </NavLink>
  );
}
