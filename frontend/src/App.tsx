import { Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { hasRole } from "@/shared/auth/keycloak";
import ConnectionStatus from "@/shared/components/ConnectionStatus";

const CanvasPage = lazy(() => import("@/features/canvas/components/Canvas"));
const DashboardPage = lazy(() => import("@/features/dashboards/components/DashboardGrid"));
const EmbedPage = lazy(() => import("@/features/embed/EmbedRoot"));

function RequireEditorRole({ children }: { children: React.ReactNode }) {
  const canEdit = hasRole("admin") || hasRole("analyst");
  if (!canEdit) {
    return <Navigate to="/dashboards" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  const isViewer = !hasRole("admin") && !hasRole("analyst");

  return (
    <Suspense fallback={<LoadingScreen />}>
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
