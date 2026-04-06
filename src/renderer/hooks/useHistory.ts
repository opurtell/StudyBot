import { useApi } from "./useApi";
import type { QuizAttempt } from "../types/api";

interface UseHistoryResult {
  entries: QuizAttempt[] | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useHistory(limit = 20): UseHistoryResult {
  const { data, loading, error, refetch } = useApi<QuizAttempt[]>(
    `/quiz/history?limit=${limit}`
  );
  return { entries: data, loading, error, refetch };
}
