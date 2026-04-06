import { useCallback } from "react";
import type { CategoryMastery, StreakResponse } from "../types/api";
import { apiGet, getApiErrorMessage } from "../lib/apiClient";
import { useCachedResource } from "./useCachedResource";

interface UseMasteryResult {
  categories: CategoryMastery[];
  streak: number;
  accuracy: number;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

const RETRIES = 3;

export function useMastery(): UseMasteryResult {
  const fetchAll = useCallback(async () => {
    try {
      const [masteryData, streakData] = await Promise.all([
        apiGet<CategoryMastery[]>("/quiz/mastery", { retries: RETRIES }),
        apiGet<StreakResponse>("/quiz/streak", { retries: RETRIES }),
      ]);
      return {
        categories: masteryData ?? [],
        streak: streakData?.streak ?? 0,
        accuracy: streakData?.accuracy ?? 0,
      };
    } catch (err) {
      throw new Error(getApiErrorMessage(err));
    }
  }, []);

  const { data, loading, refreshing, error, refetch } = useCachedResource(
    "/quiz/dashboard-mastery",
    fetchAll
  );

  return {
    categories: data?.categories ?? [],
    streak: data?.streak ?? 0,
    accuracy: data?.accuracy ?? 0,
    loading: loading || refreshing,
    error,
    refetch: () => {
      void refetch();
    },
  };
}
