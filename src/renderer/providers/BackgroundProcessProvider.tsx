import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { apiGet } from "../lib/apiClient";

export interface ActiveProcess {
  id: string;
  label: string;
}

interface BackgroundProcessContextValue {
  activeProcesses: ActiveProcess[];
  isSeeding: boolean;
  isRebuilding: boolean;
}

const BackgroundProcessContext = createContext<BackgroundProcessContextValue | null>(null);

const POLL_INTERVAL_MS = 3000;

export function BackgroundProcessProvider({ children }: { children: ReactNode }) {
  const [seedStatus, setSeedStatus] = useState<{ is_seeding: boolean; status: string } | null>(null);
  const [rebuildStatus, setRebuildStatus] = useState<{ is_running: boolean; status: string } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatuses = useCallback(async () => {
    try {
      const [seed, rebuild] = await Promise.all([
        apiGet<{ is_seeding: boolean; status: string }>("/settings/seed-status"),
        apiGet<{ is_running: boolean; status: string }>("/settings/cmg-rebuild-status"),
      ]);
      setSeedStatus(seed);
      setRebuildStatus(rebuild);
    } catch {
      // Backend may not be ready yet — swallow and retry next poll
    }
  }, []);

  const isSeeding = seedStatus?.is_seeding === true;
  const isRebuilding = rebuildStatus?.is_running === true;
  const anyActive = isSeeding || isRebuilding;

  useEffect(() => {
    fetchStatuses();

    if (anyActive) {
      if (pollRef.current !== null) return;
      pollRef.current = setInterval(fetchStatuses, POLL_INTERVAL_MS);
    } else {
      if (pollRef.current !== null) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }

    return () => {
      if (pollRef.current !== null) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [anyActive, fetchStatuses]);

  const activeProcesses = useMemo<ActiveProcess[]>(() => {
    const processes: ActiveProcess[] = [];
    if (isSeeding) {
      processes.push({ id: "seed", label: "Indexing clinical guidelines" });
    }
    if (isRebuilding) {
      processes.push({ id: "rebuild", label: "Rebuilding search index" });
    }
    return processes;
  }, [isSeeding, isRebuilding]);

  const value = useMemo<BackgroundProcessContextValue>(
    () => ({ activeProcesses, isSeeding, isRebuilding }),
    [activeProcesses, isSeeding, isRebuilding]
  );

  return (
    <BackgroundProcessContext.Provider value={value}>
      {children}
    </BackgroundProcessContext.Provider>
  );
}

export function useBackgroundProcesses() {
  const context = useContext(BackgroundProcessContext);
  if (!context) {
    throw new Error("useBackgroundProcesses must be used within a BackgroundProcessProvider");
  }
  return context;
}
