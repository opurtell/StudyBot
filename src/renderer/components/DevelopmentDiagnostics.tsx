import { useEffect, useMemo, useState } from "react";
import { useBackendStatus } from "../hooks/useBackendStatus";
import { isDevDiagnosticsEnabled, useDevDiagnostics } from "../lib/devDiagnostics";
import { useResourceCacheStore } from "../providers/ResourceCacheProvider";

function formatAge(timestamp: number | null) {
  if (timestamp === null) {
    return "never";
  }

  const deltaMs = Math.max(0, Date.now() - timestamp);
  if (deltaMs < 1000) {
    return "just now";
  }
  if (deltaMs < 60000) {
    return `${Math.floor(deltaMs / 1000)}s ago`;
  }
  if (deltaMs < 3600000) {
    return `${Math.floor(deltaMs / 60000)}m ago`;
  }
  return `${Math.floor(deltaMs / 3600000)}h ago`;
}

function formatDuration(durationMs: number | null | undefined) {
  if (durationMs === null || durationMs === undefined) {
    return "n/a";
  }
  return `${durationMs} ms`;
}

export default function DevelopmentDiagnostics() {
  const status = useBackendStatus();
  const diagnostics = useDevDiagnostics();
  const store = useResourceCacheStore();
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState(() => store.getEntries());

  useEffect(() => {
    return store.subscribeAll(() => {
      setEntries(store.getEntries());
    });
  }, [store]);

  const cacheEntries = useMemo(
    () =>
      entries
        .filter(({ snapshot }) => snapshot.loaded || snapshot.loading || snapshot.error)
        .sort((left, right) => (right.snapshot.updatedAt ?? 0) - (left.snapshot.updatedAt ?? 0))
        .slice(0, 8),
    [entries]
  );

  if (!isDevDiagnosticsEnabled()) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 z-[70] flex flex-col items-end gap-2">
      <button
        type="button"
        data-testid="dev-diagnostics-toggle"
        onClick={() => setOpen((current) => !current)}
        className="bg-surface-container-high px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-on-surface shadow-ambient"
      >
        {open ? "Hide Diagnostics" : "Diagnostics"}
      </button>

      {open && (
        <div
          data-testid="dev-diagnostics-panel"
          className="flex max-h-[calc(100vh-6rem)] w-[360px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden bg-surface-container-low shadow-ambient"
        >
          <div className="flex items-center justify-between border-b border-outline-variant/10 px-4 py-3">
            <div className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant">
              Development Diagnostics
            </div>
            <button
              type="button"
              data-testid="dev-diagnostics-close"
              onClick={() => setOpen(false)}
              className="font-mono text-[10px] uppercase tracking-widest text-on-surface"
            >
              Close
            </button>
          </div>

          <div
            data-testid="dev-diagnostics-scroll"
            className="space-y-4 overflow-y-auto px-4 py-4"
          >
            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant">
                  Backend
                </h3>
                <span className="font-mono text-[10px] text-on-surface">{status.state}</span>
              </div>
              <div className="space-y-1 font-mono text-[10px] text-on-surface-variant">
                <div>Launch #{status.diagnostics?.launchId ?? 0}</div>
                <div>Startup {formatDuration(status.diagnostics?.startupDurationMs)}</div>
                <div>Health checks {status.diagnostics?.healthCheckAttempts ?? 0}</div>
                <div>{status.message ?? "No backend error"}</div>
              </div>
            </section>

            <section className="space-y-2">
              <h3 className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant">
                Recent Requests
              </h3>
              <div className="space-y-2">
                {diagnostics.requests.length === 0 && (
                  <div className="font-mono text-[10px] text-on-surface-variant">
                    No request diagnostics yet
                  </div>
                )}
                {diagnostics.requests.slice(0, 5).map((request) => (
                  <div key={request.id} className="bg-surface px-2 py-2">
                    <div className="flex items-center justify-between font-mono text-[10px] text-on-surface">
                      <span>{request.method} {request.path}</span>
                      <span>{request.status}</span>
                    </div>
                    <div className="mt-1 font-mono text-[10px] text-on-surface-variant">
                      {formatDuration(request.durationMs)} total, gate {formatDuration(request.gateDurationMs)}
                    </div>
                    <div className="font-mono text-[10px] text-on-surface-variant">
                      {request.category ?? `HTTP ${request.httpStatus ?? "n/a"}`}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="space-y-2">
              <h3 className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant">
                Cache Freshness
              </h3>
              <div className="space-y-2">
                {cacheEntries.length === 0 && (
                  <div className="font-mono text-[10px] text-on-surface-variant">
                    No cached resources yet
                  </div>
                )}
                {cacheEntries.map(({ key, snapshot }) => (
                  <div key={key} className="bg-surface px-2 py-2">
                    <div className="flex items-center justify-between font-mono text-[10px] text-on-surface">
                      <span>{key}</span>
                      <span>{snapshot.error ? "error" : snapshot.refreshing ? "refreshing" : snapshot.loaded ? "ready" : "pending"}</span>
                    </div>
                    <div className="mt-1 font-mono text-[10px] text-on-surface-variant">
                      Updated {formatAge(snapshot.updatedAt)}
                    </div>
                    <div className="font-mono text-[10px] text-on-surface-variant">
                      Last attempt {formatAge(snapshot.lastAttemptAt)}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
