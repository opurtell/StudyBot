import { costMicros, type LlmResult } from "../llm/gemini";
import { currentQuotaPeriod, quotaLimits } from "../lib/quota";
import { PROMPT_VERSION } from "./prompts";

export type CreditKind = "gen" | "eval";

const COLUMN: Record<CreditKind, { used: string; other: string }> = {
  gen: { used: "free_gen_used", other: "free_eval_used" },
  eval: { used: "free_eval_used", other: "free_gen_used" },
};

type QuotaEnv = Pick<Env, "QUOTA_GENERATIONS_PER_MONTH" | "QUOTA_MARKS_PER_MONTH">;

export function creditLimit(env: QuotaEnv, kind: CreditKind): number {
  const limits = quotaLimits(env);
  return kind === "gen" ? limits.generations : limits.marking;
}

export async function takeCredit(db: D1Database, env: QuotaEnv, userId: string, kind: CreditKind, now: Date): Promise<boolean> {
  const { used, other } = COLUMN[kind];
  const period = currentQuotaPeriod(now);
  const row = await db
    .prepare(
      `UPDATE users SET
         ${used} = CASE WHEN quota_period = ?2 THEN ${used} + 1 ELSE 1 END,
         ${other} = CASE WHEN quota_period = ?2 THEN ${other} ELSE 0 END,
         quota_period = ?2
       WHERE id = ?1 AND ?3 > 0 AND (quota_period != ?2 OR ${used} < ?3)
       RETURNING id`,
    )
    .bind(userId, period, creditLimit(env, kind))
    .first<{ id: string }>();
  return row !== null;
}

export async function refundCredit(db: D1Database, userId: string, kind: CreditKind, now: Date): Promise<void> {
  const { used } = COLUMN[kind];
  await db
    .prepare(`UPDATE users SET ${used} = ${used} - 1 WHERE id = ?1 AND quota_period = ?2 AND ${used} > 0`)
    .bind(userId, currentQuotaPeriod(now))
    .run();
}

export async function readQuota(db: D1Database, userId: string) {
  return db
    .prepare(`SELECT quota_period, free_gen_used, free_eval_used FROM users WHERE id = ?1`)
    .bind(userId)
    .first<{ quota_period: string; free_gen_used: number; free_eval_used: number }>()
    .then((row) => ({
      quotaPeriod: row?.quota_period ?? "",
      freeGenUsed: row?.free_gen_used ?? 0,
      freeEvalUsed: row?.free_eval_used ?? 0,
    }));
}

export type Outcome = "ok" | "unreadable" | "error";

export function ledgerStatement(
  db: D1Database,
  entry: {
    userId: string | null;
    kind: CreditKind;
    outcome: Outcome;
    modelId: string;
    questionId?: string | null;
    result?: LlmResult | null;
    now: number;
  },
): D1PreparedStatement {
  const usage = entry.result?.usage ?? { inputTokens: 0, outputTokens: 0, thinkingTokens: 0, cachedInputTokens: 0 };
  return db
    .prepare(
      `INSERT INTO usage_ledger (id, user_id, kind, outcome, model_id, prompt_version, question_id, tokens_in, tokens_out,
         tokens_thinking, tokens_cached, cost_usd_micros, cache_hit, gateway_log_id, latency_ms, created_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16)`,
    )
    .bind(
      crypto.randomUUID(),
      entry.userId,
      entry.kind,
      entry.outcome,
      entry.modelId,
      PROMPT_VERSION,
      entry.questionId ?? null,
      usage.inputTokens,
      usage.outputTokens,
      usage.thinkingTokens,
      usage.cachedInputTokens,
      entry.result ? costMicros(entry.result.modelId, usage) : 0,
      entry.result?.cacheHit ? 1 : 0,
      entry.result?.gatewayLogId ?? null,
      entry.result?.latencyMs ?? null,
      entry.now,
    );
}

export function startOfUtcDay(now: number): number {
  const d = new Date(now);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

function parseCap(value: string | undefined, fallback: number): number {
  const n = Number.parseInt(value ?? "", 10);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
}

export function dailyCaps(env: Pick<Env, "DAILY_GENERATIONS_CAP" | "DAILY_MARKS_CAP">): Record<CreditKind, number> {
  return { gen: parseCap(env.DAILY_GENERATIONS_CAP, 200), eval: parseCap(env.DAILY_MARKS_CAP, 1000) };
}

export async function usedToday(db: D1Database, kind: CreditKind, now: number): Promise<number> {
  const row = await db
    .prepare(`SELECT calls FROM daily_usage WHERE day = ?1 AND kind = ?2`)
    .bind(startOfUtcDay(now), kind)
    .first<{ calls: number }>();
  return row?.calls ?? 0;
}

export const LIVE_AI_FLAG = "live_ai";

export async function liveAiEnabled(db: D1Database): Promise<boolean> {
  const row = await db.prepare(`SELECT value FROM app_flags WHERE key = ?1`).bind(LIVE_AI_FLAG).first<{ value: string }>();
  return row?.value !== "off";
}

export async function setLiveAi(db: D1Database, enabled: boolean, now: number): Promise<void> {
  await db
    .prepare(
      `INSERT INTO app_flags (key, value, updated_at) VALUES (?1, ?2, ?3)
       ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`,
    )
    .bind(LIVE_AI_FLAG, enabled ? "on" : "off", now)
    .run();
}

export type Availability = { ok: true } | { ok: false; reason: "paused" | "daily_cap" | "not_configured" };

export async function liveAiAvailability(
  env: Pick<Env, "DB" | "GEMINI_API_KEY" | "DAILY_GENERATIONS_CAP" | "DAILY_MARKS_CAP">,
  kind: CreditKind,
  now: number,
): Promise<Availability> {
  if (!env.GEMINI_API_KEY) return { ok: false, reason: "not_configured" };
  if (!(await liveAiEnabled(env.DB))) return { ok: false, reason: "paused" };
  if ((await usedToday(env.DB, kind, now)) >= dailyCaps(env)[kind]) return { ok: false, reason: "daily_cap" };
  return { ok: true };
}
