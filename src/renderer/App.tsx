import { HashRouter, Routes, Route, Outlet } from "react-router-dom";
import { ThemeProvider } from "./hooks/useTheme";
import AppShell from "./components/AppShell";
import Dashboard from "./pages/Dashboard";
import Quiz from "./pages/Quiz";
import Feedback from "./pages/Feedback";
import Library from "./pages/Library";
import Medication from "./pages/Medication";
import Settings from "./pages/Settings";
import Guidelines from "./pages/Guidelines";
import BackendBootGate from "./components/BackendBootGate";
import ErrorBoundary from "./components/ErrorBoundary";
import { BackendStatusProvider } from "./hooks/useBackendStatus";
import { ResourceCacheProvider, ServiceNamespacedCache } from "./providers/ResourceCacheProvider";
import { SettingsProvider } from "./providers/SettingsProvider";
import { ServiceProvider } from "./providers/ServiceProvider";
import { BackgroundProcessProvider } from "./providers/BackgroundProcessProvider";
import { ServiceSetupModal } from "./components/ServiceSetupModal";
import { useService } from "./hooks/useService";

function StandardLayout() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/library" element={<Library />} />
        <Route path="/medication" element={<Medication />} />
        <Route path="/guidelines" element={<Guidelines />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </AppShell>
  );
}

function FocusLayout() {
  return (
    <div className="min-h-screen bg-background text-on-surface">
      <div className="fixed inset-0 dot-grid" />
      <main className="min-h-screen relative z-10">
        <Outlet />
      </main>
    </div>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/quiz" element={<FocusLayout />}>
        <Route index element={<Quiz />} />
      </Route>
      <Route path="/feedback" element={<FocusLayout />}>
        <Route index element={<Feedback />} />
      </Route>
      <Route path="/*" element={<StandardLayout />} />
    </Routes>
  );
}

function ServiceSetupGate({ children }: { children: React.ReactNode }) {
  const { activeService } = useService();
  const showSetupModal = !activeService;

  return (
    <>
      {children}
      {showSetupModal && <ServiceSetupModal open={true} />}
    </>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <BackendStatusProvider>
        <ResourceCacheProvider>
          <SettingsProvider>
            <ServiceProvider>
            <ServiceNamespacedCache>
            <BackgroundProcessProvider>
            <ServiceSetupGate>
            <HashRouter>
              <BackendBootGate>
                <ErrorBoundary>
                  <AppRoutes />
                </ErrorBoundary>
              </BackendBootGate>
            </HashRouter>
            </ServiceSetupGate>
            </BackgroundProcessProvider>
            </ServiceNamespacedCache>
            </ServiceProvider>
          </SettingsProvider>
        </ResourceCacheProvider>
      </BackendStatusProvider>
    </ThemeProvider>
  );
}
