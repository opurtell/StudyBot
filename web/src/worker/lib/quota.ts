export function currentQuotaPeriod(now: Date = new Date()): string {
  return now.toISOString().slice(0, 7);
}

export interface QuotaSummary {
  period: string;
  generations: { used: number; limit: number; remaining: number };
  marking: { used: number; limit: number; remaining: number };
}

function parseLimit(value: string | undefined, fallback: number): number {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

export function quotaLimits(env: Pick<Env, "QUOTA_GENERATIONS_PER_MONTH" | "QUOTA_MARKS_PER_MONTH">) {
  return {
    generations: parseLimit(env.QUOTA_GENERATIONS_PER_MONTH, 20),
    marking: parseLimit(env.QUOTA_MARKS_PER_MONTH, 30),
  };
}

export function summariseQuota(
  env: Pick<Env, "QUOTA_GENERATIONS_PER_MONTH" | "QUOTA_MARKS_PER_MONTH">,
  user: { quotaPeriod: string; freeGenUsed: number; freeEvalUsed: number },
  now: Date = new Date(),
): QuotaSummary {
  const limits = quotaLimits(env);
  const period = currentQuotaPeriod(now);
  const stale = user.quotaPeriod !== period;
  const genUsed = stale ? 0 : user.freeGenUsed;
  const evalUsed = stale ? 0 : user.freeEvalUsed;
  return {
    period,
    generations: { used: genUsed, limit: limits.generations, remaining: Math.max(0, limits.generations - genUsed) },
    marking: { used: evalUsed, limit: limits.marking, remaining: Math.max(0, limits.marking - evalUsed) },
  };
}
