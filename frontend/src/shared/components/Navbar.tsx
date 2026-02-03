/**
 * Shared navigation bar — appears on Canvas and Dashboard pages.
 * Provides links between modes and user menu.
 */

import { Link, useLocation } from "react-router-dom";
import { getCurrentUser, hasRole, logout } from "@/shared/auth/keycloak";

export default function Navbar() {
  const location = useLocation();
  const user = getCurrentUser();
  const canEdit = hasRole("admin") || hasRole("analyst");

  const isActive = (path: string) => location.pathname.startsWith(path);

  return (
    <header className="h-12 bg-canvas-node border-b border-canvas-border flex items-center px-4 shrink-0 justify-between">
      <div className="flex items-center gap-6">
        <Link to="/" className="text-sm font-semibold tracking-wide text-white">
          FlowForge
        </Link>

        <nav className="flex items-center gap-1">
          {canEdit && (
            <Link
              to="/canvas"
              className={`px-3 py-1.5 text-xs rounded transition-colors ${
                isActive("/canvas")
                  ? "bg-canvas-accent text-white"
                  : "text-white/60 hover:text-white hover:bg-white/5"
              }`}
            >
              Canvas
            </Link>
          )}
          <Link
            to="/dashboards"
            className={`px-3 py-1.5 text-xs rounded transition-colors ${
              isActive("/dashboards")
                ? "bg-canvas-accent text-white"
                : "text-white/60 hover:text-white hover:bg-white/5"
            }`}
          >
            Dashboards
          </Link>
        </nav>
      </div>

      <div className="flex items-center gap-3">
        {user && (
          <span className="text-xs text-white/40">{user.email}</span>
        )}
        <button
          onClick={() => logout()}
          className="text-xs text-white/40 hover:text-white transition-colors"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
