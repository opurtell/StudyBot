import { useCallback, useState } from "react";
import { apiGet, apiPost, apiDelete, getApiErrorMessage } from "../lib/apiClient";
import { useCachedResource } from "./useCachedResource";

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useApi<T>(path: string, retries = 3): UseApiResult<T> {
  const cached = useCachedResource<T>(
    path ? `${path}::${retries}` : "",
    async (signal) => {
      try {
        const result = await apiGet<T>(path, { retries, signal });
        if (signal.aborted) {
          throw new DOMException("Request aborted", "AbortError");
        }
        return result ?? null;
      } catch (err) {
        if (signal.aborted) {
          throw new DOMException("Request aborted", "AbortError");
        }
        throw new Error(getApiErrorMessage(err));
      }
    },
    { enabled: Boolean(path) }
  );

  const refetch = useCallback(async () => {
    await cached.refetch();
  }, [cached]);

  return {
    data: cached.data,
    loading: cached.loading || cached.refreshing,
    error: cached.error,
    refetch,
  };
}

interface UseApiMutationResult<T, B> {
  execute: (body: B) => Promise<T | null>;
  loading: boolean;
  error: string | null;
}

export function useApiMutation<T, B>(
  method: "POST" | "DELETE",
  path: string
): UseApiMutationResult<T, B> {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(
    async (body: B) => {
      setLoading(true);
      setError(null);
      try {
        if (method === "DELETE" && typeof body === "string") {
          await apiDelete<void>(`${path}/${encodeURIComponent(body)}`);
          return null;
        }
        return await apiPost<T>(path, body);
      } catch (err) {
        setError(getApiErrorMessage(err));
        return null;
      } finally {
        setLoading(false);
      }
    },
    [method, path]
  );

  return { execute, loading, error };
}
