import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { recordCacheDiagnostic } from "../lib/devDiagnostics";
import { useService } from "../hooks/useService";

export interface ResourceSnapshot<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  refreshing: boolean;
  loaded: boolean;
  updatedAt: number | null;
  lastAttemptAt: number | null;
  lastSuccessAt: number | null;
  lastErrorAt: number | null;
}

interface CacheStore {
  getSnapshot: <T>(key: string) => ResourceSnapshot<T>;
  getEntries: () => Array<{ key: string; snapshot: ResourceSnapshot<unknown> }>;
  subscribe: (key: string, listener: () => void) => () => void;
  subscribeAll: (listener: () => void) => () => void;
  fetchResource: <T>(
    key: string,
    fetcher: (signal: AbortSignal) => Promise<T | null>,
    options?: { force?: boolean }
  ) => Promise<T | null>;
  setData: <T>(key: string, data: T | null) => void;
  setError: (key: string, error: string | null) => void;
  invalidate: (key: string) => void;
}

const defaultSnapshot: ResourceSnapshot<never> = {
  data: null,
  error: null,
  loading: false,
  refreshing: false,
  loaded: false,
  updatedAt: null,
  lastAttemptAt: null,
  lastSuccessAt: null,
  lastErrorAt: null,
};

const ResourceCacheContext = createContext<CacheStore | null>(null);
const STORAGE_KEY = "studybot.resource-cache.v2";
const PERSISTED_KEY_PREFIXES = ["/guidelines/"];
const PERSISTED_KEYS = new Set([
  "/guidelines::3",
  "/medication/doses::4",
  "/quiz/dashboard-mastery",
  "/quiz/history?limit=3::3",
  "/settings/models",
]);

interface PersistedSnapshot {
  data: unknown;
  updatedAt: number;
}

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function shouldPersist(key: string) {
  if (PERSISTED_KEYS.has(key)) {
    return true;
  }
  return PERSISTED_KEY_PREFIXES.some((prefix) => key.startsWith(prefix));
}

function toPersistedSnapshot(
  snapshot: ResourceSnapshot<unknown>
): PersistedSnapshot | null {
  if (!snapshot.loaded || snapshot.data === null || snapshot.updatedAt === null) {
    return null;
  }
  return {
    data: snapshot.data,
    updatedAt: snapshot.updatedAt,
  };
}

function readPersistedEntries() {
  const entries = new Map<string, ResourceSnapshot<unknown>>();
  if (!canUseStorage()) {
    return entries;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return entries;
    }
    const parsed = JSON.parse(raw) as Record<string, PersistedSnapshot>;
    for (const [key, snapshot] of Object.entries(parsed)) {
      if (
        !snapshot ||
        typeof snapshot.updatedAt !== "number" ||
        !Object.prototype.hasOwnProperty.call(snapshot, "data")
      ) {
        continue;
      }
      entries.set(key, {
        data: snapshot.data,
        error: null,
        loading: false,
        refreshing: false,
        loaded: true,
        updatedAt: snapshot.updatedAt,
        lastAttemptAt: snapshot.updatedAt,
        lastSuccessAt: snapshot.updatedAt,
        lastErrorAt: null,
      });
    }
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
  }

  return entries;
}

function writePersistedEntries(entries: Map<string, ResourceSnapshot<unknown>>) {
  if (!canUseStorage()) {
    return;
  }

  const persisted: Record<string, PersistedSnapshot> = {};
  for (const [key, snapshot] of entries.entries()) {
    if (!shouldPersist(key)) {
      continue;
    }
    const serializable = toPersistedSnapshot(snapshot);
    if (serializable) {
      persisted[key] = serializable;
    }
  }

  if (Object.keys(persisted).length === 0) {
    window.localStorage.removeItem(STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted));
}

/** Inner cache store that manages raw entries without service namespacing. */
export function ResourceCacheProviderInner({ children }: { children: ReactNode }) {
  const [, setVersion] = useState(0);
  const entriesRef = useRef(readPersistedEntries());
  const listenersRef = useRef(new Map<string, Set<() => void>>());
  const allListenersRef = useRef(new Set<() => void>());
  const inflightRef = useRef(
    new Map<string, { controller: AbortController; promise: Promise<unknown | null> }>()
  );

  const notify = useCallback((key: string) => {
    setVersion((current) => current + 1);
    listenersRef.current.get(key)?.forEach((listener) => listener());
    allListenersRef.current.forEach((listener) => listener());
  }, []);

  const getSnapshot = useCallback(<T,>(key: string): ResourceSnapshot<T> => {
    const existing = entriesRef.current.get(key);
    if (!existing) {
      return defaultSnapshot as ResourceSnapshot<T>;
    }
    return existing as ResourceSnapshot<T>;
  }, []);

  const getEntries = useCallback(() => {
    return Array.from(entriesRef.current.entries()).map(([key, snapshot]) => ({
      key,
      snapshot,
    }));
  }, []);

  const subscribe = useCallback((key: string, listener: () => void) => {
    const listeners = listenersRef.current.get(key) ?? new Set<() => void>();
    listeners.add(listener);
    listenersRef.current.set(key, listeners);
    return () => {
      const current = listenersRef.current.get(key);
      if (!current) {
        return;
      }
      current.delete(listener);
      if (current.size === 0) {
        listenersRef.current.delete(key);
      }
    };
  }, []);

  const subscribeAll = useCallback((listener: () => void) => {
    allListenersRef.current.add(listener);
    return () => {
      allListenersRef.current.delete(listener);
    };
  }, []);

  const setData = useCallback(
    <T,>(key: string, data: T | null) => {
      const now = Date.now();
      entriesRef.current.set(key, {
        data,
        error: null,
        loading: false,
        refreshing: false,
        loaded: true,
        updatedAt: now,
        lastAttemptAt: now,
        lastSuccessAt: now,
        lastErrorAt: null,
      });
      recordCacheDiagnostic({
        key,
        event: "set-data",
        durationMs: null,
        ageMs: 0,
        message: null,
      });
      writePersistedEntries(entriesRef.current);
      notify(key);
    },
    [notify]
  );

  const setError = useCallback(
    (key: string, error: string | null) => {
      const previous = getSnapshot(key);
      entriesRef.current.set(key, {
        ...previous,
        error,
        loading: false,
        refreshing: false,
        lastErrorAt: error ? Date.now() : previous.lastErrorAt,
      });
      recordCacheDiagnostic({
        key,
        event: error ? "set-error" : "clear-error",
        durationMs: null,
        ageMs: previous.updatedAt === null ? null : Date.now() - previous.updatedAt,
        message: error,
      });
      notify(key);
    },
    [getSnapshot, notify]
  );

  const invalidate = useCallback(
    (key: string) => {
      inflightRef.current.get(key)?.controller.abort();
      inflightRef.current.delete(key);
      entriesRef.current.delete(key);
      recordCacheDiagnostic({
        key,
        event: "invalidate",
        durationMs: null,
        ageMs: null,
        message: null,
      });
      writePersistedEntries(entriesRef.current);
      notify(key);
    },
    [notify]
  );

  const fetchResource = useCallback(
    async <T,>(
      key: string,
      fetcher: (signal: AbortSignal) => Promise<T | null>,
      options?: { force?: boolean }
    ) => {
      const fetchStartedAt = Date.now();
      if (!options?.force) {
        const inflight = inflightRef.current.get(key);
        if (inflight) {
          recordCacheDiagnostic({
            key,
            event: "inflight-reuse",
            durationMs: null,
            ageMs: null,
            message: null,
          });
          return (await inflight.promise) as T | null;
        }
      }

      if (options?.force) {
        inflightRef.current.get(key)?.controller.abort();
        inflightRef.current.delete(key);
        recordCacheDiagnostic({
          key,
          event: "force-refresh",
          durationMs: null,
          ageMs: null,
          message: null,
        });
      }

      const previous = getSnapshot<T>(key);
      const attemptAt = Date.now();
      entriesRef.current.set(key, {
        data: previous.data,
        error: null,
        loading: !previous.loaded,
        refreshing: previous.loaded,
        loaded: previous.loaded,
        updatedAt: previous.updatedAt,
        lastAttemptAt: attemptAt,
        lastSuccessAt: previous.lastSuccessAt,
        lastErrorAt: previous.lastErrorAt,
      });
      recordCacheDiagnostic({
        key,
        event: previous.loaded ? "refresh-start" : "fetch-start",
        durationMs: null,
        ageMs: previous.updatedAt === null ? null : attemptAt - previous.updatedAt,
        message: null,
      });
      notify(key);

      const controller = new AbortController();
      const promise = fetcher(controller.signal)
        .then((data) => {
          if (controller.signal.aborted) {
            return previous.data;
          }
          const resolvedAt = Date.now();
          entriesRef.current.set(key, {
            data,
            error: null,
            loading: false,
            refreshing: false,
            loaded: true,
            updatedAt: resolvedAt,
            lastAttemptAt: attemptAt,
            lastSuccessAt: resolvedAt,
            lastErrorAt: null,
          });
          recordCacheDiagnostic({
            key,
            event: "fetch-success",
            durationMs: resolvedAt - fetchStartedAt,
            ageMs: 0,
            message: null,
          });
          writePersistedEntries(entriesRef.current);
          notify(key);
          return data;
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) {
            return previous.data;
          }
          const message = error instanceof Error ? error.message : "Unknown error";
          const resolvedAt = Date.now();
          entriesRef.current.set(key, {
            data: previous.data,
            error: message,
            loading: false,
            refreshing: false,
            loaded: previous.loaded,
            updatedAt: previous.updatedAt,
            lastAttemptAt: attemptAt,
            lastSuccessAt: previous.lastSuccessAt,
            lastErrorAt: resolvedAt,
          });
          recordCacheDiagnostic({
            key,
            event: "fetch-error",
            durationMs: resolvedAt - fetchStartedAt,
            ageMs: previous.updatedAt === null ? null : resolvedAt - previous.updatedAt,
            message,
          });
          notify(key);
          return previous.data;
        })
        .finally(() => {
          const inflight = inflightRef.current.get(key);
          if (inflight?.controller === controller) {
            inflightRef.current.delete(key);
          }
        });

      inflightRef.current.set(key, { controller, promise });
      return (await promise) as T | null;
    },
    [getSnapshot, notify]
  );

  const store = useMemo<CacheStore>(
    () => ({
      getSnapshot,
      getEntries,
      subscribe,
      subscribeAll,
      fetchResource,
      setData,
      setError,
      invalidate,
    }),
    [fetchResource, getEntries, getSnapshot, invalidate, setData, setError, subscribe, subscribeAll]
  );

  return <ResourceCacheContext.Provider value={store}>{children}</ResourceCacheContext.Provider>;
}

/**
 * Wrapper that reads the active service and provides a CacheStore that
 * namespaces all keys with the service ID (`serviceId:originalKey`).
 * When the active service changes, all keys change, naturally invalidating
 * cached data from the previous service.
 *
 * Must be rendered inside both ResourceCacheProviderInner and ServiceProvider.
 */
export function ServiceNamespacedCache({ children }: { children: ReactNode }) {
  const innerStore = useContext(ResourceCacheContext);
  const { activeService } = useService();
  const serviceId = activeService?.id ?? "__no_service__";

  const namespacedStore = useMemo<CacheStore>(() => {
    if (!innerStore) {
      throw new Error("ServiceNamespacedCache must be used within ResourceCacheProviderInner");
    }

    const prefixKey = (key: string) => `${serviceId}:${key}`;

    return {
      getSnapshot: <T,>(key: string) => innerStore.getSnapshot<T>(prefixKey(key)),
      getEntries: () =>
        innerStore.getEntries().filter((e) => e.key.startsWith(`${serviceId}:`)),
      subscribe: (key: string, listener: () => void) =>
        innerStore.subscribe(prefixKey(key), listener),
      subscribeAll: (listener: () => void) => innerStore.subscribeAll(listener),
      fetchResource: <T,>(
        key: string,
        fetcher: (signal: AbortSignal) => Promise<T | null>,
        options?: { force?: boolean }
      ) => innerStore.fetchResource<T>(prefixKey(key), fetcher, options),
      setData: <T,>(key: string, data: T | null) =>
        innerStore.setData<T>(prefixKey(key), data),
      setError: (key: string, error: string | null) =>
        innerStore.setError(prefixKey(key), error),
      invalidate: (key: string) => innerStore.invalidate(prefixKey(key)),
    };
  }, [innerStore, serviceId]);

  return (
    <ResourceCacheContext.Provider value={namespacedStore}>
      {children}
    </ResourceCacheContext.Provider>
  );
}

/**
 * Public cache provider. Renders the inner store which holds the raw cache
 * data. The ServiceNamespacedCache wrapper (placed inside ServiceProvider in
 * the app tree) handles key prefixing.
 */
export function ResourceCacheProvider({ children }: { children: ReactNode }) {
  return <ResourceCacheProviderInner>{children}</ResourceCacheProviderInner>;
}

export function useResourceCacheStore() {
  const context = useContext(ResourceCacheContext);
  if (!context) {
    throw new Error("useResourceCacheStore must be used within a ResourceCacheProvider");
  }
  return context;
}
