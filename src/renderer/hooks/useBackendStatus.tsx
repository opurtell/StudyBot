import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { BackendStatusPayload } from "../types/backend";

const initialStatus: BackendStatusPayload = { state: "starting", message: null };
const BackendStatusContext = createContext<BackendStatusPayload | null>(null);
const BackendStatusActionContext = createContext<{
  refresh: () => Promise<BackendStatusPayload>;
  restart: () => Promise<BackendStatusPayload>;
} | null>(null);

export function BackendStatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<BackendStatusPayload>(initialStatus);

  useEffect(() => {
    let mounted = true;
    let unsubscribe: (() => void) | undefined;

    const backend = window.api?.backend;
    if (!backend) {
      setStatus({ state: "ready", message: null });
      return () => {
        mounted = false;
      };
    }

    backend
      .getStatus()
      .then((current) => {
        if (!mounted) return;
        setStatus(current);
        unsubscribe = backend.onStatusChange((next) => {
          if (mounted) {
            setStatus(next);
          }
        });
      })
      .catch((error) => {
        if (mounted) {
          const message = error instanceof Error ? error.message : String(error);
          setStatus({ state: "error", message });
        }
      });

    return () => {
      mounted = false;
      unsubscribe?.();
    };
  }, []);

  const refresh = useCallback(async () => {
    const backend = window.api?.backend;
    if (!backend) {
      const readyStatus: BackendStatusPayload = { state: "ready", message: null };
      setStatus(readyStatus);
      return readyStatus;
    }

    const latestStatus = await backend.getStatus();
    setStatus(latestStatus);
    return latestStatus;
  }, []);

  const restart = useCallback(async () => {
    const backend = window.api?.backend;
    if (!backend) {
      const readyStatus: BackendStatusPayload = { state: "ready", message: null };
      setStatus(readyStatus);
      return readyStatus;
    }

    setStatus({ state: "starting", message: "Launching backend" });
    const latestStatus = await backend.restart();
    setStatus(latestStatus);
    return latestStatus;
  }, []);

  const actions = useMemo(() => ({ refresh, restart }), [refresh, restart]);

  return (
    <BackendStatusContext.Provider value={status}>
      <BackendStatusActionContext.Provider value={actions}>{children}</BackendStatusActionContext.Provider>
    </BackendStatusContext.Provider>
  );
}

export function useBackendStatus() {
  const context = useContext(BackendStatusContext);
  if (context === null) {
    throw new Error("useBackendStatus must be used within a BackendStatusProvider");
  }
  return context;
}

export function useBackendStatusActions() {
  const context = useContext(BackendStatusActionContext);
  if (!context) {
    throw new Error("useBackendStatusActions must be used within a BackendStatusProvider");
  }
  return context;
}
