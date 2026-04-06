import { ReactNode } from "react";
import Sidebar from "./Sidebar";
import SearchBar from "./SearchBar";
import { useBackendStatus } from "../hooks/useBackendStatus";
import DevelopmentDiagnostics from "./DevelopmentDiagnostics";

interface AppShellProps {
  children: ReactNode;
}

const statusConfig = {
  ready: {
    label: "System Active",
    dot: "bg-status-success",
  },
  starting: {
    label: "Starting backend",
    dot: "bg-status-caution",
  },
  error: {
    label: "Backend unavailable",
    dot: "bg-status-critical",
  },
  stopped: {
    label: "Backend inactive",
    dot: "bg-outline",
  },
};

export default function AppShell({ children }: AppShellProps) {
  const status = useBackendStatus();
  const current = statusConfig[status.state] ?? statusConfig.ready;
  const message = status.state === "ready" ? null : status.message ?? current.label;
  return (
    <>
      <div className="fixed inset-0 dot-grid" />

      <Sidebar />

      <main className="ml-64 min-h-screen p-8 lg:p-12 max-w-7xl relative z-10">
        <div className="mb-8">
          <SearchBar placeholder="Search the archive..." />
        </div>

        {children}

        <footer className="mt-24 pt-8 border-t border-outline-variant/10 flex justify-between items-center">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <div className={`w-1.5 h-1.5 rounded-full ${current.dot}`} />
              <span
                className="font-mono text-[10px] text-on-surface-variant"
                title={status.message ?? undefined}
              >
                {current.label}
              </span>
            </div>
            {message && (
              <span className="font-mono text-[10px] text-on-surface-variant">
                {message}
              </span>
            )}
          </div>
        </footer>
      </main>

      <DevelopmentDiagnostics />
    </>
  );
}
