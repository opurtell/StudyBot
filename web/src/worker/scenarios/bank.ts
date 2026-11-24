import { VIEWS, type CorpusView } from "../corpus/repo";
import { apViewFor } from "../quiz/scope";
import { PATIENT_GROUPS, type PatientGroup, type RubricPoint, type Score } from "../../shared/scenarios";

const SERVICE = "actas";
export const DIFFICULTIES = ["easy", "medium", "hard"] as const;
export type Difficulty = (typeof DIFFICULTIES)[number];
export const FLAG_KEY = "scenarios_enabled";
export type Audience = "admins" | "everyone";

export interface StoredStage {
  ordinal: number;
  reveal: string;
  question: string;
  focus: string;
  rubric: { point: string; critical: boolean; cites: { chunk_id: string; document_id: string; quote: string }[] }[];
}

export interface PublicStage {
  ordinal: number;
  reveal: string;
  question: string;
  focus: string;
}

export interface ScenarioFilters {
  category: string | null;
  difficulty: Difficulty | null;
  patientGroup: PatientGroup | null;
  icpOnly: boolean;
}

export interface ScenarioRow {
  id: string;
  title: string;
  dispatch_text: string;
  category: string;
  difficulty: Difficulty;
  patient_group: PatientGroup;
  primary_document_id: string;
  document_title: string | null;
  stages_json: string;
}

function visColumn(view: CorpusView): string {
  if (!(VIEWS as readonly string[]).includes(view)) throw new Error(`bad view ${view}`);
  return `vis_${view}`;
}

const FRESH = `NOT EXISTS (
  SELECT 1 FROM scenario_sources s LEFT JOIN corpus_chunks c ON c.id = s.chunk_id AND c.retired_at IS NULL
  WHERE s.scenario_id = b.id AND c.id IS NULL)`;

function scopeSql(view: CorpusView, icpOnly: boolean): string {
  const vis = visColumn(view);
  if (!icpOnly) return `b.${vis} = 1`;
  const ap = apViewFor(view);
  if (!ap) throw new Error(`icpOnly needs an ICP view, got ${view}`);
  return `b.${vis} = 1 AND b.${visColumn(ap)} = 0`;
}

export function parseStages(json: string): StoredStage[] {
  return JSON.parse(json) as StoredStage[];
}

export function publicStage(stage: StoredStage): PublicStage {
  return { ordinal: stage.ordinal, reveal: stage.reveal, question: stage.question, focus: stage.focus };
}

export function publicRubric(stage: StoredStage): RubricPoint[] {
  return stage.rubric.map((p) => ({
    point: p.point,
    critical: p.critical,
    cites: p.cites.map((c) => ({ chunkId: c.chunk_id, documentId: c.document_id, quote: c.quote })),
  }));
}

const SELECT = `SELECT b.id, b.title, b.dispatch_text, b.category, b.difficulty, b.patient_group, b.primary_document_id,
  d.title AS document_title, b.stages_json
  FROM scenario_bank b LEFT JOIN corpus_documents d ON d.id = b.primary_document_id`;

function where(view: CorpusView, f: ScenarioFilters): { sql: string; params: unknown[] } {
  return {
    sql: `WHERE b.service = ?1 AND b.status = 'active' AND ${scopeSql(view, f.icpOnly)} AND ${FRESH}
      AND (?2 IS NULL OR b.category = ?2) AND (?3 IS NULL OR b.difficulty = ?3) AND (?4 IS NULL OR b.patient_group = ?4)`,
    params: [SERVICE, f.category, f.difficulty, f.patientGroup],
  };
}

export async function nextScenario(
  db: D1Database,
  opts: { view: CorpusView; filters: ScenarioFilters; userId: string | null; exclude: string[]; repeat: boolean },
): Promise<ScenarioRow | null> {
  const w = where(opts.view, opts.filters);
  const params = [...w.params, opts.userId, JSON.stringify(opts.exclude)];
  if (opts.repeat) {
    return db
      .prepare(
        `${SELECT} ${w.sql}
         ORDER BY (SELECT s.last_seen_at FROM user_scenario_seen s WHERE s.user_id = ?5 AND s.scenario_id = b.id) NULLS FIRST,
           random() LIMIT 1`,
      )
      .bind(...w.params, opts.userId)
      .first<ScenarioRow>();
  }
  const unseen = `AND (?5 IS NULL OR NOT EXISTS (SELECT 1 FROM user_scenario_seen s WHERE s.user_id = ?5 AND s.scenario_id = b.id))
    AND b.id NOT IN (SELECT value FROM json_each(?6))`;
  const start = Math.random();
  const pick = (bound: string) =>
    db.prepare(`${SELECT} ${w.sql} ${unseen} AND ${bound} ORDER BY b.rand_key LIMIT 1`).bind(...params, start).first<ScenarioRow>();
  return (await pick("b.rand_key >= ?7")) ?? (await pick("b.rand_key < ?7"));
}

export async function getScenario(db: D1Database, id: string, view: CorpusView): Promise<ScenarioRow | null> {
  return db
    .prepare(`${SELECT} WHERE b.id = ?1 AND b.status = 'active' AND b.${visColumn(view)} = 1 AND ${FRESH}`)
    .bind(id)
    .first<ScenarioRow>();
}

export async function recordSeen(db: D1Database, scenarioId: string, userId: string | null, now: number): Promise<void> {
  const stmts = [db.prepare(`UPDATE scenario_bank SET times_served = times_served + 1 WHERE id = ?1`).bind(scenarioId)];
  if (userId) {
    stmts.push(
      db
        .prepare(
          `INSERT INTO user_scenario_seen (user_id, scenario_id, first_seen_at, last_seen_at) VALUES (?1, ?2, ?3, ?3)
           ON CONFLICT (user_id, scenario_id) DO UPDATE SET last_seen_at = excluded.last_seen_at`,
        )
        .bind(userId, scenarioId, now),
    );
  }
  await db.batch(stmts);
}

export interface OptionCount {
  category: string;
  difficulty: Difficulty;
  patientGroup: PatientGroup;
  count: number;
}

export async function scenarioOptions(db: D1Database, view: CorpusView, icpOnly: boolean): Promise<OptionCount[]> {
  const { results } = await db
    .prepare(
      `SELECT b.category, b.difficulty, b.patient_group AS patientGroup, COUNT(*) AS count FROM scenario_bank b
       WHERE b.service = ?1 AND b.status = 'active' AND ${scopeSql(view, icpOnly)} AND ${FRESH}
       GROUP BY 1, 2, 3 ORDER BY 1, 2, 3`,
    )
    .bind(SERVICE)
    .all<OptionCount>();
  return results;
}

export async function insertAttempt(
  db: D1Database,
  a: { userId: string; scenarioId: string; view: CorpusView; stages: unknown; score: Score },
  now: number,
): Promise<string> {
  const id = crypto.randomUUID();
  await db
    .prepare(
      `INSERT INTO scenario_attempts (id, user_id, scenario_id, view, stage_results_json, score, created_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)`,
    )
    .bind(id, a.userId, a.scenarioId, a.view, JSON.stringify(a.stages), a.score, now)
    .run();
  return id;
}

export async function retireStaleScenarios(db: D1Database, now: number): Promise<number> {
  const result = await db
    .prepare(
      `UPDATE scenario_bank SET status = 'retired', status_reason = 'source_changed', updated_at = ?1
       WHERE status != 'retired' AND NOT ${FRESH.replace(/b\.id/g, "scenario_bank.id")}`,
    )
    .bind(now)
    .run();
  return result.meta.changes ?? 0;
}

export async function scenarioAudience(db: D1Database): Promise<Audience> {
  const row = await db.prepare(`SELECT value FROM app_flags WHERE key = ?1`).bind(FLAG_KEY).first<{ value: string }>();
  return row?.value === "everyone" ? "everyone" : "admins";
}

export async function setScenarioAudience(db: D1Database, audience: Audience, now: number): Promise<void> {
  await db
    .prepare(
      `INSERT INTO app_flags (key, value, updated_at) VALUES (?1, ?2, ?3)
       ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`,
    )
    .bind(FLAG_KEY, audience, now)
    .run();
}

export async function scenarioExists(db: D1Database, id: string): Promise<boolean> {
  return (await db.prepare(`SELECT 1 FROM scenario_bank WHERE id = ?1`).bind(id).first()) !== null;
}

export async function reportsToday(db: D1Database, reporterKey: string, startOfDay: number): Promise<number> {
  const row = await db
    .prepare(`SELECT COUNT(*) AS n FROM scenario_reports WHERE reporter_key = ?1 AND created_at >= ?2`)
    .bind(reporterKey, startOfDay)
    .first<{ n: number }>();
  return row?.n ?? 0;
}

export async function reportScenario(
  db: D1Database,
  r: { scenarioId: string; stage: number | null; userId: string | null; reporterKey: string; reason: string; detail: string | null; flagNow: boolean; threshold: number },
  now: number,
): Promise<{ flagged: boolean }> {
  await db
    .prepare(
      `INSERT INTO scenario_reports (id, scenario_id, stage, user_id, reporter_key, reason, detail, created_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
       ON CONFLICT (scenario_id, reporter_key) DO UPDATE SET reason = excluded.reason, detail = excluded.detail,
         stage = excluded.stage, created_at = excluded.created_at, resolved_at = NULL`,
    )
    .bind(crypto.randomUUID(), r.scenarioId, r.stage, r.userId, r.reporterKey, r.reason, r.detail, now)
    .run();
  const row = await db
    .prepare(
      `SELECT COUNT(DISTINCT reporter_key) AS n FROM scenario_reports
       WHERE scenario_id = ?1 AND resolved_at IS NULL AND reporter_key LIKE 'user:%'`,
    )
    .bind(r.scenarioId)
    .first<{ n: number }>();
  const flagged = r.flagNow || (row?.n ?? 0) >= r.threshold;
  await db
    .prepare(
      `UPDATE scenario_bank SET times_reported = times_reported + 1, updated_at = ?2,
         status = CASE WHEN ?3 = 1 AND status = 'active' THEN 'flagged' ELSE status END,
         status_reason = CASE WHEN ?3 = 1 AND status = 'active' THEN 'reported' ELSE status_reason END
       WHERE id = ?1`,
    )
    .bind(r.scenarioId, now, flagged ? 1 : 0)
    .run();
  return { flagged };
}

export async function adminSummary(db: D1Database) {
  const [counts, reported] = await Promise.all([
    db.prepare(`SELECT status, COUNT(*) AS n FROM scenario_bank GROUP BY status`).all<{ status: string; n: number }>(),
    db
      .prepare(
        `SELECT b.id, b.title, b.status, b.status_reason, COUNT(r.id) AS reports
         FROM scenario_bank b JOIN scenario_reports r ON r.scenario_id = b.id AND r.resolved_at IS NULL
         GROUP BY b.id ORDER BY reports DESC LIMIT 50`,
      )
      .all<{ id: string; title: string; status: string; status_reason: string | null; reports: number }>(),
  ]);
  return {
    byStatus: Object.fromEntries(counts.results.map((r) => [r.status, r.n])),
    reported: reported.results,
  };
}

export async function setScenarioStatus(db: D1Database, id: string, status: "active" | "retired", now: number): Promise<boolean> {
  const res = await db
    .prepare(
      `UPDATE scenario_bank SET status = ?2, status_reason = CASE WHEN ?2 = 'active' THEN NULL ELSE 'admin' END, updated_at = ?3
       WHERE id = ?1`,
    )
    .bind(id, status, now)
    .run();
  if (status === "active") {
    await db.prepare(`UPDATE scenario_reports SET resolved_at = ?2 WHERE scenario_id = ?1 AND resolved_at IS NULL`).bind(id, now).run();
  }
  return (res.meta.changes ?? 0) > 0;
}

export function isPatientGroup(value: unknown): value is PatientGroup {
  return typeof value === "string" && (PATIENT_GROUPS as readonly string[]).includes(value);
}
