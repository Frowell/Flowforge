import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { lazy, Suspense } from "react";
import { hasRole } from "@/shared/auth/keycloak";
import ConnectionStatus from "@/shared/components/ConnectionStatus";
import Navbar from "@/shared/components/Navbar";

const CanvasPage = lazy(() => import("@/features/canvas/components/Canvas"));
const DashboardPage = lazy(() => import("@/features/dashboards/components/DashboardGrid"));
const EmbedPage = lazy(() => import("@/features/embed/EmbedRoot"));
const AuditLogPage = lazy(() => import("@/features/admin/AuditLogPage"));

function RequireEditorRole({ children }: { children: React.ReactNode }) {
  const canEdit = hasRole("admin") || hasRole("analyst");
  if (!canEdit) {
    return <Navigate to="/dashboards" replace />;
  }
  return <>{children}</>;
}

function RequireAdminRole({ children }: { children: React.ReactNode }) {
  if (!hasRole("admin")) {
    return <Navigate to="/dashboards" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  const location = useLocation();
  const isViewer = !hasRole("admin") && !hasRole("analyst");
  const isEmbed = location.pathname.startsWith("/embed");

  return (
    <Suspense fallback={<LoadingScreen />}>
      {!isEmbed && <Navbar />}
      <Routes>
        <Route
          path="/canvas"
          element={
            <RequireEditorRole>
              <CanvasPage />
            </RequireEditorRole>
          }
        />
        <Route
          path="/canvas/:workflowId"
          element={
            <RequireEditorRole>
              <CanvasPage />
            </RequireEditorRole>
          }
        />
        <Route path="/dashboards" element={<DashboardPage />} />
        <Route path="/dashboards/:dashboardId" element={<DashboardPage />} />
        <Route path="/embed/:widgetId" element={<EmbedPage />} />
        <Route
          path="/admin/audit"
          element={
            <RequireAdminRole>
              <AuditLogPage />
            </RequireAdminRole>
          }
        />
        <Route path="*" element={<Navigate to={isViewer ? "/dashboards" : "/canvas"} replace />} />
      </Routes>
      <ConnectionStatus />
    </Suspense>
  );
}

function LoadingScreen() {
  return (
    <div className="h-screen w-screen flex items-center justify-center bg-canvas-bg">
      <div className="text-white/50 text-sm">Loading...</div>
    </div>
  );
}
