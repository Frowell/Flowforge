import { Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";

const CanvasPage = lazy(() => import("@/features/canvas/components/Canvas"));
const DashboardPage = lazy(() => import("@/features/dashboards/components/DashboardGrid"));
const EmbedPage = lazy(() => import("@/features/embed/EmbedRoot"));

export default function App() {
  return (
    <Suspense fallback={<LoadingScreen />}>
      <Routes>
        <Route path="/canvas" element={<CanvasPage />} />
        <Route path="/canvas/:workflowId" element={<CanvasPage />} />
        <Route path="/dashboards" element={<DashboardPage />} />
        <Route path="/dashboards/:dashboardId" element={<DashboardPage />} />
        <Route path="/embed/:widgetId" element={<EmbedPage />} />
        <Route path="*" element={<Navigate to="/canvas" replace />} />
      </Routes>
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
