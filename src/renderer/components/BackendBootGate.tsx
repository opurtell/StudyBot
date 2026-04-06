import type { ReactNode } from "react";
import { useBackendStatus, useBackendStatusActions } from "../hooks/useBackendStatus";

interface BackendBootGateProps {
  children: ReactNode;
}

export default function BackendBootGate({ children }: BackendBootGateProps) {
  const status = useBackendStatus();
  const { restart } = useBackendStatusActions();

  if (status.state === "starting") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-6 bg-background px-6 text-on-surface text-center">
        <p className="font-headline text-headline-sm">Preparing clinical data services</p>
        <p className="text-sm text-on-surface-variant max-w-xl">
          Loading your study data. This should take only a moment.
        </p>
        <div className="w-48 rounded-full bg-surface-container">
          <div className="h-1 rounded-full bg-primary w-10 animate-pulse" />
        </div>
        <p className="text-xs uppercase tracking-[0.3em] text-on-surface-variant">Stand by</p>
      </div>
    );
  }

  if (status.state === "error" || status.state === "stopped") {
    const label = status.state === "error" ? "Backend unavailable" : "Backend stopped";
    const detail = status.message ?? "Local clinical services are offline. Retry when the backend is ready.";
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-background px-6 text-on-surface text-center">
        <p className="font-headline text-headline-sm">{label}</p>
        <p className="text-sm text-on-surface-variant max-w-xl">{detail}</p>
        <button
          type="button"
          className="px-6 py-3 rounded-full bg-primary text-on-primary font-label text-sm"
          onClick={() => restart()}
        >
          Retry
        </button>
      </div>
    );
  }

  return <>{children}</>;
}
