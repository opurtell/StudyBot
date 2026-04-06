import { useCallback, useEffect, useState } from "react";
import { useResourceCacheStore, type ResourceSnapshot } from "../providers/ResourceCacheProvider";
import { recordCacheDiagnostic } from "../lib/devDiagnostics";

interface UseCachedResourceOptions {
  enabled?: boolean;
}

interface UseCachedResourceResult<T> extends ResourceSnapshot<T> {
  refetch: () => Promise<T | null>;
}

export function useCachedResource<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T | null>,
  options?: UseCachedResourceOptions
): UseCachedResourceResult<T> {
  const store = useResourceCacheStore();
  const enabled = options?.enabled ?? true;
  const [snapshot, setSnapshot] = useState<ResourceSnapshot<T>>(() =>
    enabled
      ? store.getSnapshot<T>(key)
      : {
          data: null,
          error: null,
        loading: false,
        refreshing: false,
        loaded: false,
        updatedAt: null,
        lastAttemptAt: null,
        lastSuccessAt: null,
        lastErrorAt: null,
      }
  );

  useEffect(() => {
    if (!enabled) {
      setSnapshot({
        data: null,
        error: null,
        loading: false,
        refreshing: false,
        loaded: false,
        updatedAt: null,
        lastAttemptAt: null,
        lastSuccessAt: null,
        lastErrorAt: null,
      });
      return;
    }

    const current = store.getSnapshot<T>(key);
    setSnapshot(current);
    recordCacheDiagnostic({
      key,
      event: current.loaded ? "access-hit" : "access-miss",
      durationMs: null,
      ageMs: current.updatedAt === null ? null : Date.now() - current.updatedAt,
      message: null,
    });
    return store.subscribe(key, () => {
      setSnapshot(store.getSnapshot<T>(key));
    });
  }, [enabled, key, store]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    const current = store.getSnapshot<T>(key);
    if (current.loaded || current.loading || current.refreshing) {
      return;
    }
    void store.fetchResource(key, fetcher);
  }, [enabled, fetcher, key, store]);

  const refetch = useCallback(async () => {
    if (!enabled) {
      return null;
    }
    return await store.fetchResource(key, fetcher, { force: true });
  }, [enabled, fetcher, key, store]);

  return {
    ...snapshot,
    refetch,
  };
}
