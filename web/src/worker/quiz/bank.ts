import { sha256Hex } from "../lib/crypto";
import { CORPUS_SERVICE, VIEWS, type CorpusView } from "../corpus/repo";
import type { Difficulty, QuestionType } from "./prompts";
import type { Visibility } from "./scope";

export interface QuestionFilters {
  documentId: string | null;
  section: string | null;
  difficulty: Difficulty | null;
}

export interface Exclusions {
  sections: string[];
  documents: string[];
}

export const NO_EXCLUSIONS: Exclusions = { sections: [], documents: [] };

export interface PublicQuestion {
  id: string;
  text: string;
  type: QuestionType;
  difficulty: Difficulty;
  category: string;
  citation: string;
  documentId: string;
  documentNumber: string;
  documentTitle: string;
  section: string;
  origin: "bank" | "live";
}

export interface StoredQuestion extends PublicQuestion {
  status: "active" | "flagged" | "retired";
  sourceText: string;
  attribution: string;
  licence: string;
}

interface QuestionRow {
  id: string;
  question_text: string;
  question_type: QuestionType;
  difficulty: Difficulty;
  category: string;
  source_citation: string;
  document_id: string;
  number: string;
  title: string;
  section: string;
  origin: "bank" | "live";
  status: StoredQuestion["status"];
  source_text: string;
  attribution: string;
  licence: string;
}

const SELECT_QUESTION = `SELECT q.id, q.question_text, q.question_type, q.difficulty, q.category, q.source_citation, q.document_id,
  d.number, d.title, d.section, q.origin, q.status, q.source_text, q.attribution, q.licence
  FROM question_bank q
  JOIN corpus_documents d ON d.id = q.document_id
  JOIN corpus_chunks c ON c.id = q.chunk_id AND c.retired_at IS NULL AND c.embed_text = q.source_text`;

function toPublic(row: QuestionRow): PublicQuestion {
  return {
    id: row.id,
    text: row.question_text,
    type: row.question_type,
    difficulty: row.difficulty,
    category: row.category,
    citation: row.source_citation,
    documentId: row.document_id,
    documentNumber: row.number,
    documentTitle: row.title,
    section: row.section,
    origin: row.origin,
  };
}

function toStored(row: QuestionRow): StoredQuestion {
  return { ...toPublic(row), status: row.status, sourceText: row.source_text, attribution: row.attribution, licence: row.licence };
}

function exclusionSql(sections: string, documents: string): string {
  return `AND d.section NOT IN (SELECT value FROM json_each(${sections}))
         AND d.id NOT IN (SELECT value FROM json_each(${documents}))`;
}

function exclusionParams(filters: Pick<QuestionFilters, "documentId" | "section">, exclusions?: Exclusions): [string, string] {
  if (!exclusions || filters.documentId) return ["[]", "[]"];
  return [JSON.stringify(filters.section ? [] : exclusions.sections), JSON.stringify(exclusions.documents)];
}

function visColumn(view: CorpusView): string {
  if (!(VIEWS as readonly string[]).includes(view)) throw new Error(`bad view ${view}`);
  return `vis_${view}`;
}

export async function nextQuestion(
  db: D1Database,
  opts: {
    view: CorpusView;
    filters: QuestionFilters;
    userId: string | null;
    exclude: string[];
    repeat: boolean;
    exclusions?: Exclusions;
  },
): Promise<PublicQuestion | null> {
  const vis = visColumn(opts.view);
  const where = `WHERE q.service = ?1 AND q.status = 'active' AND q.${vis} = 1 AND c.${vis} = 1
         AND (?2 IS NULL OR q.document_id = ?2)
         AND (?3 IS NULL OR d.section = ?3)
         AND (?4 IS NULL OR q.difficulty = ?4)
         ${exclusionSql("?7", "?8")}`;
  const params = [
    CORPUS_SERVICE,
    opts.filters.documentId,
    opts.filters.section,
    opts.filters.difficulty,
    opts.userId,
    JSON.stringify(opts.exclude),
    ...exclusionParams(opts.filters, opts.exclusions),
  ];

  if (opts.repeat) {
    const row = await db
      .prepare(
        `${SELECT_QUESTION}
         ${where}
           AND ?6 IS NOT NULL
         ORDER BY (SELECT s.last_seen_at FROM user_question_seen s WHERE s.user_id = ?5 AND s.question_id = q.id) NULLS FIRST, random()
         LIMIT 1`,
      )
      .bind(...params)
      .first<QuestionRow>();
    return row ? toPublic(row) : null;
  }

  const fromSql = opts.filters.documentId
    ? SELECT_QUESTION
    : SELECT_QUESTION.replace("FROM question_bank q", "FROM question_bank q INDEXED BY question_bank_rand");
  const unseen = `AND (?5 IS NULL OR NOT EXISTS (SELECT 1 FROM user_question_seen s WHERE s.user_id = ?5 AND s.question_id = q.id))
         AND q.id NOT IN (SELECT value FROM json_each(?6))`;
  const start = Math.random();
  const pick = (bound: string) =>
    db
      .prepare(`${fromSql} ${where} ${unseen} AND ${bound} ORDER BY q.rand_key LIMIT 1`)
      .bind(...params, start)
      .first<QuestionRow>();
  const row = (await pick("q.rand_key >= ?9")) ?? (await pick("q.rand_key < ?9"));
  return row ? toPublic(row) : null;
}

export async function getQuestion(db: D1Database, id: string, view: CorpusView): Promise<StoredQuestion | null> {
  const vis = visColumn(view);
  const row = await db
    .prepare(`${SELECT_QUESTION} WHERE q.id = ?1 AND q.${vis} = 1 AND c.${vis} = 1`)
    .bind(id)
    .first<QuestionRow>();
  return row ? toStored(row) : null;
}

export async function recordServed(db: D1Database, questionId: string, userId: string | null, now: number): Promise<void> {
  const stmts = [
    db
      .prepare(`UPDATE question_bank SET times_served = times_served + 1, rand_key = ?2 WHERE id = ?1`)
      .bind(questionId, Math.random() * 0.999999 + 0.000001),
  ];
  if (userId) {
    stmts.push(
      db
        .prepare(
          `INSERT INTO user_question_seen (user_id, question_id, first_seen_at, last_seen_at) VALUES (?1, ?2, ?3, ?3)
           ON CONFLICT (user_id, question_id) DO UPDATE SET last_seen_at = excluded.last_seen_at`,
        )
        .bind(userId, questionId, now),
    );
  }
  await db.batch(stmts);
}

export function normaliseQuestion(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export async function questionHash(text: string): Promise<string> {
  return sha256Hex(normaliseQuestion(text));
}

export interface CandidateChunk {
  id: string;
  documentId: string;
  embedText: string;
  section: string;
  visibility: Visibility;
}

export async function candidateChunks(
  db: D1Database,
  view: CorpusView,
  filters: Pick<QuestionFilters, "documentId" | "section">,
  limit = 5,
  exclusions?: Exclusions,
): Promise<CandidateChunk[]> {
  const vis = visColumn(view);
  const { results } = await db
    .prepare(
      `SELECT c.id, c.document_id, c.embed_text, d.section, c.vis_ap, c.vis_ap_pacer, c.vis_icp, c.vis_icp_pacer
       FROM corpus_chunks c JOIN corpus_documents d ON d.id = c.document_id
       WHERE c.retired_at IS NULL AND c.${vis} = 1 AND length(c.text) >= 200 AND d.service = ?1
         AND (?2 IS NULL OR c.document_id = ?2)
         AND (?3 IS NULL OR d.section = ?3)
         ${exclusionSql("?5", "?6")}
       ORDER BY (SELECT COUNT(*) FROM question_bank q WHERE q.chunk_id = c.id AND q.status = 'active'), random()
       LIMIT ?4`,
    )
    .bind(CORPUS_SERVICE, filters.documentId, filters.section, limit, ...exclusionParams(filters, exclusions))
    .all<{
      id: string;
      document_id: string;
      embed_text: string;
      section: string;
      vis_ap: number;
      vis_ap_pacer: number;
      vis_icp: number;
      vis_icp_pacer: number;
    }>();
  return results.map((r) => ({
    id: r.id,
    documentId: r.document_id,
    embedText: r.embed_text,
    section: r.section,
    visibility: { ap: r.vis_ap === 1, ap_pacer: r.vis_ap_pacer === 1, icp: r.vis_icp === 1, icp_pacer: r.vis_icp_pacer === 1 },
  }));
}

export async function previousQuestionsFor(db: D1Database, chunkIds: string[], limit = 10): Promise<string[]> {
  const { results } = await db
    .prepare(
      `SELECT question_text FROM question_bank WHERE chunk_id IN (SELECT value FROM json_each(?1)) AND status != 'retired'
       ORDER BY created_at DESC LIMIT ?2`,
    )
    .bind(JSON.stringify(chunkIds), limit)
    .all<{ question_text: string }>();
  return results.map((r) => r.question_text);
}

export async function findByHash(db: D1Database, hash: string): Promise<{ id: string } | null> {
  return db.prepare(`SELECT id FROM question_bank WHERE content_hash = ?1`).bind(hash).first<{ id: string }>();
}

export interface NewQuestion {
  chunk: CandidateChunk;
  text: string;
  type: QuestionType;
  difficulty: Difficulty;
  category: string;
  citation: string;
  generatedFor: CorpusView;
  visibility: Visibility;
  hash: string;
  modelId: string;
  promptVersion: string;
  corpusVersion: string;
}

export async function insertLiveQuestion(db: D1Database, q: NewQuestion, now: number): Promise<string | null> {
  const id = q.hash.slice(0, 16);
  const row = await db
    .prepare(
      `INSERT INTO question_bank (id, service, document_id, chunk_id, source_text, question_text, question_type, difficulty,
         category, source_citation, gen_view, vis_ap, vis_ap_pacer, vis_icp, vis_icp_pacer, source_type, licence, attribution,
         content_hash, prompt_version, model_id, corpus_version, origin, status, created_at, updated_at)
       SELECT ?1, d.service, c.document_id, c.id, c.embed_text, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, c.source_type,
         c.licence, c.attribution, ?13, ?14, ?15, ?16, 'live', 'active', ?17, ?17
       FROM corpus_chunks c JOIN corpus_documents d ON d.id = c.document_id
       WHERE c.id = ?2 AND c.retired_at IS NULL
       ON CONFLICT DO NOTHING
       RETURNING id`,
    )
    .bind(
      id,
      q.chunk.id,
      q.text,
      q.type,
      q.difficulty,
      q.category,
      q.citation,
      q.generatedFor,
      q.visibility.ap ? 1 : 0,
      q.visibility.ap_pacer ? 1 : 0,
      q.visibility.icp ? 1 : 0,
      q.visibility.icp_pacer ? 1 : 0,
      q.hash,
      q.promptVersion,
      q.modelId,
      q.corpusVersion,
      now,
    )
    .first<{ id: string }>();
  return row?.id ?? null;
}

export async function retireStaleQuestions(db: D1Database, now: number): Promise<number> {
  const result = await db
    .prepare(
      `UPDATE question_bank SET status = 'retired', status_reason = 'source_changed', updated_at = ?1
       WHERE status != 'retired' AND NOT EXISTS (
         SELECT 1 FROM corpus_chunks c
         WHERE c.id = question_bank.chunk_id AND c.retired_at IS NULL AND c.embed_text = question_bank.source_text)`,
    )
    .bind(now)
    .run();
  return result.meta.changes ?? 0;
}

export const REPORT_REASONS = ["incorrect", "out_of_scope", "unclear", "not_in_source", "other"] as const;
export type ReportReason = (typeof REPORT_REASONS)[number];

export async function reportQuestion(
  db: D1Database,
  report: { questionId: string; userId: string | null; reporterKey: string; reason: ReportReason; detail: string | null; flagNow: boolean; threshold: number },
  now: number,
): Promise<{ flagged: boolean }> {
  await db
    .prepare(
      `INSERT INTO question_reports (id, question_id, user_id, reporter_key, reason, detail, created_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
       ON CONFLICT (question_id, reporter_key) DO UPDATE SET reason = excluded.reason, detail = excluded.detail,
         created_at = excluded.created_at, resolved_at = NULL`,
    )
    .bind(crypto.randomUUID(), report.questionId, report.userId, report.reporterKey, report.reason, report.detail, now)
    .run();
  const row = await db
    .prepare(
      `UPDATE question_bank SET
         times_reported = (SELECT COUNT(*) FROM question_reports r WHERE r.question_id = ?1 AND r.resolved_at IS NULL),
         status = CASE WHEN status = 'active' AND (?2 = 1 OR
           (SELECT COUNT(*) FROM question_reports r WHERE r.question_id = ?1 AND r.resolved_at IS NULL AND r.user_id IS NOT NULL) >= ?3)
           THEN 'flagged' ELSE status END,
         status_reason = CASE WHEN status = 'active' AND (?2 = 1 OR
           (SELECT COUNT(*) FROM question_reports r WHERE r.question_id = ?1 AND r.resolved_at IS NULL AND r.user_id IS NOT NULL) >= ?3)
           THEN 'reported' ELSE status_reason END,
         updated_at = ?4
       WHERE id = ?1
       RETURNING status`,
    )
    .bind(report.questionId, report.flagNow ? 1 : 0, report.threshold, now)
    .first<{ status: string }>();
  return { flagged: row?.status === "flagged" };
}

export async function reportsToday(db: D1Database, reporterKey: string, startOfDay: number): Promise<number> {
  const row = await db
    .prepare(`SELECT COUNT(*) AS n FROM question_reports WHERE reporter_key = ?1 AND created_at >= ?2`)
    .bind(reporterKey, startOfDay)
    .first<{ n: number }>();
  return row?.n ?? 0;
}

export async function questionExists(db: D1Database, id: string): Promise<boolean> {
  return (await db.prepare(`SELECT 1 AS x FROM question_bank WHERE id = ?1`).bind(id).first()) !== null;
}

export interface BankSummary {
  byStatus: Record<string, number>;
  activeByView: Record<CorpusView, number>;
  activeByDifficulty: Record<string, number>;
  live: number;
}

export async function bankSummary(db: D1Database): Promise<BankSummary> {
  const [status, views, difficulty] = await db.batch([
    db.prepare(`SELECT status AS k, COUNT(*) AS n FROM question_bank GROUP BY status`),
    db.prepare(
      `SELECT SUM(vis_ap) AS ap, SUM(vis_ap_pacer) AS ap_pacer, SUM(vis_icp) AS icp, SUM(vis_icp_pacer) AS icp_pacer,
         SUM(origin = 'live') AS live
       FROM question_bank WHERE status = 'active'`,
    ),
    db.prepare(`SELECT difficulty AS k, COUNT(*) AS n FROM question_bank WHERE status = 'active' GROUP BY difficulty`),
  ]);
  const pairs = (r: D1Result | undefined) =>
    Object.fromEntries(((r?.results ?? []) as { k: string; n: number }[]).map((x) => [x.k, x.n]));
  const v = (views?.results[0] ?? {}) as Record<string, number | null>;
  return {
    byStatus: pairs(status),
    activeByView: { ap: v.ap ?? 0, ap_pacer: v.ap_pacer ?? 0, icp: v.icp ?? 0, icp_pacer: v.icp_pacer ?? 0 },
    activeByDifficulty: pairs(difficulty),
    live: v.live ?? 0,
  };
}

export interface ReportedQuestion {
  id: string;
  text: string;
  status: string;
  statusReason: string | null;
  citation: string;
  documentId: string;
  sourceText: string;
  origin: string;
  reports: { reason: string; detail: string | null; createdAt: number }[];
}

export async function reportedQuestions(db: D1Database, limit = 50): Promise<ReportedQuestion[]> {
  const { results } = await db
    .prepare(
      `SELECT q.id, q.question_text, q.status, q.status_reason, q.source_citation, q.document_id, q.source_text, q.origin,
         (SELECT json_group_array(json_object('reason', r.reason, 'detail', r.detail, 'createdAt', r.created_at))
            FROM question_reports r WHERE r.question_id = q.id AND r.resolved_at IS NULL) AS reports
       FROM question_bank q
       WHERE q.status = 'flagged' OR EXISTS (SELECT 1 FROM question_reports r WHERE r.question_id = q.id AND r.resolved_at IS NULL)
       ORDER BY q.updated_at DESC LIMIT ?1`,
    )
    .bind(limit)
    .all<{
      id: string;
      question_text: string;
      status: string;
      status_reason: string | null;
      source_citation: string;
      document_id: string;
      source_text: string;
      origin: string;
      reports: string;
    }>();
  return results.map((r) => ({
    id: r.id,
    text: r.question_text,
    status: r.status,
    statusReason: r.status_reason,
    citation: r.source_citation,
    documentId: r.document_id,
    sourceText: r.source_text,
    origin: r.origin,
    reports: JSON.parse(r.reports) as ReportedQuestion["reports"],
  }));
}

export async function setQuestionStatus(
  db: D1Database,
  id: string,
  status: "active" | "retired",
  now: number,
): Promise<boolean> {
  const [update] = await db.batch([
    db
      .prepare(
        `UPDATE question_bank SET status = ?2, status_reason = ?3, times_reported = 0, updated_at = ?4 WHERE id = ?1`,
      )
      .bind(id, status, status === "retired" ? "admin_retired" : "admin_restored", now),
    db.prepare(`UPDATE question_reports SET resolved_at = ?2 WHERE question_id = ?1 AND resolved_at IS NULL`).bind(id, now),
  ]);
  return (update?.meta.changes ?? 0) > 0;
}
