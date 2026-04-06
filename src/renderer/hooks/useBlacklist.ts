import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiDelete, getApiErrorMessage } from "../lib/apiClient";

interface UseBlacklistResult {
  items: string[];
  loading: boolean;
  error: string | null;
  add: (name: string) => Promise<void>;
  remove: (name: string) => Promise<void>;
  refetch: () => void;
}

export function useBlacklist(): UseBlacklistResult {
  const [items, setItems] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet<string[]>("/quiz/blacklist");
      setItems(data ?? []);
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  const add = useCallback(
    async (name: string) => {
      try {
        await apiPost("/quiz/blacklist", { category_name: name });
        await fetchItems();
      } catch (err) {
        setError(getApiErrorMessage(err));
      }
    },
    [fetchItems]
  );

  const remove = useCallback(
    async (name: string) => {
      try {
        await apiDelete<void>(`/quiz/blacklist/${encodeURIComponent(name)}`);
        await fetchItems();
      } catch (err) {
        setError(getApiErrorMessage(err));
      }
    },
    [fetchItems]
  );

  return { items, loading, error, add, remove, refetch: fetchItems };
}
