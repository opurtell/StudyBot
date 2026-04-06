import { useSyncExternalStore } from "react";

export interface RequestDiagnostic {
  id: number;
  path: string;
  method: string;
  attempt: number;
  startedAt: string;
  finishedAt: string;
  durationMs: number;
  gateDurationMs: number;
  status: "success" | "error" | "aborted";
  httpStatus: number | null;
  category: string | null;
  message: string | null;
}

export interface CacheDiagnostic {
  id: number;
  key: string;
  event: string;
  at: string;
  durationMs: number | null;
  ageMs: number | null;
  message: string | null;
}

export interface DevDiagnosticsSnapshot {
  requests: RequestDiagnostic[];
  cacheEvents: CacheDiagnostic[];
}

const diagnosticsEnabled = import.meta.env.DEV;
const logToConsole = diagnosticsEnabled && import.meta.env.MODE !== "test";
const listeners = new Set<() => void>();

let requestId = 0;
let cacheEventId = 0;
let snapshot: DevDiagnosticsSnapshot = {
  requests: [],
  cacheEvents: [],
};

function emit() {
  for (const listener of listeners) {
    listener();
  }
}

function pushRecent<T>(items: T[], next: T, maxItems = 30) {
  return [next, ...items].slice(0, maxItems);
}

export function isDevDiagnosticsEnabled() {
  return diagnosticsEnabled;
}

export function clearDevDiagnostics() {
  snapshot = {
    requests: [],
    cacheEvents: [],
  };
  emit();
}

export function getDevDiagnosticsSnapshot() {
  return snapshot;
}

export function subscribeToDevDiagnostics(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function recordRequestDiagnostic(
  entry: Omit<RequestDiagnostic, "id" | "startedAt" | "finishedAt"> & {
    startedAt?: string;
    finishedAt?: string;
  }
) {
  if (!diagnosticsEnabled) {
    return;
  }

  const next: RequestDiagnostic = {
    id: ++requestId,
    startedAt: entry.startedAt ?? new Date().toISOString(),
    finishedAt: entry.finishedAt ?? new Date().toISOString(),
    ...entry,
  };

  snapshot = {
    ...snapshot,
    requests: pushRecent(snapshot.requests, next),
  };

  if (logToConsole) {
    console.debug("[renderer-request]", next);
  }
  emit();
}

export function recordCacheDiagnostic(
  entry: Omit<CacheDiagnostic, "id" | "at"> & {
    at?: string;
  }
) {
  if (!diagnosticsEnabled) {
    return;
  }

  const next: CacheDiagnostic = {
    id: ++cacheEventId,
    at: entry.at ?? new Date().toISOString(),
    ...entry,
  };

  snapshot = {
    ...snapshot,
    cacheEvents: pushRecent(snapshot.cacheEvents, next),
  };

  if (logToConsole) {
    console.debug("[renderer-cache]", next);
  }
  emit();
}

export function useDevDiagnostics() {
  return useSyncExternalStore(
    subscribeToDevDiagnostics,
    getDevDiagnosticsSnapshot,
    getDevDiagnosticsSnapshot
  );
}
