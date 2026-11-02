import type { CorpusView } from "../corpus/repo";
import type { Score } from "../../shared/progress";

const RANK: Record<Score, number> = { incorrect: 0, partial: 1, correct: 2 };

export type OverrideDirection = "model_too_harsh" | "model_too_lenient";

export function overrideDirection(modelScore: Score, userScore: Score): OverrideDirection | null {
  if (RANK[userScore] === RANK[modelScore]) return null;
  return RANK[userScore] > RANK[modelScore] ? "model_too_harsh" : "model_too_lenient";
}

interface MarkedAttempt {
  question_id: string;
  user_answer: string | null;
  evaluation_json: string;
  model_id: string | null;
  prompt_version: string | null;
  created_at: number;
}

function modelScoreOf(evaluationJson: string): Score | null {
  try {
    const score = (JSON.parse(evaluationJson) as { score?: unknown }).score;
    return score === "correct" || score === "partial" || score === "incorrect" ? score : null;
  } catch {
    return null;
  }
}

export async function recordOverride(
  db: D1Database,
  input: { attemptId: string; userId: string; userScore: Score; view: CorpusView | null },
  now: number,
): Promise<OverrideDirection | null> {
  const attempt = await db
    .prepare(
      `SELECT question_id, user_answer, evaluation_json, model_id, prompt_version, created_at
       FROM attempts WHERE id = ?1 AND user_id = ?2 AND kind = 'marked' AND evaluation_json IS NOT NULL`,
    )
    .bind(input.attemptId, input.userId)
    .first<MarkedAttempt>();
  if (!attempt) return null;
  const modelScore = modelScoreOf(attempt.evaluation_json);
  if (!modelScore) return null;
  const direction = overrideDirection(modelScore, input.userScore);
  if (!direction) {
    await db.prepare(`DELETE FROM marking_overrides WHERE attempt_id = ?1`).bind(input.attemptId).run();
    return null;
  }
  await db
    .prepare(
      `INSERT INTO marking_overrides (
         id, attempt_id, user_id, question_id, document_id, document_title, section, category, citation, question_origin,
         question_text, source_text, view, user_answer, model_score, user_score, direction, evaluation_json, model_id,
         prompt_version, marked_at, created_at, updated_at)
       SELECT ?1, ?2, ?3, ?4, q.document_id, d.title, d.section, q.category, q.source_citation, q.origin,
         q.question_text, q.source_text, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?14
       FROM (SELECT 1) LEFT JOIN question_bank q ON q.id = ?4 LEFT JOIN corpus_documents d ON d.id = q.document_id
       ON CONFLICT (attempt_id) DO UPDATE SET
         user_score = excluded.user_score, direction = excluded.direction, view = COALESCE(excluded.view, view),
         updated_at = excluded.updated_at`,
    )
    .bind(
      crypto.randomUUID(),
      input.attemptId,
      input.userId,
      attempt.question_id,
      input.view,
      attempt.user_answer,
      modelScore,
      input.userScore,
      direction,
      attempt.evaluation_json,
      attempt.model_id,
      attempt.prompt_version,
      attempt.created_at,
      now,
    )
    .run();
  return direction;
}

export interface OverrideRecord {
  id: string;
  attemptId: string;
  userId: string;
  questionId: string;
  documentId: string | null;
  documentTitle: string | null;
  section: string | null;
  category: string | null;
  citation: string | null;
  questionOrigin: string | null;
  questionText: string | null;
  sourceText: string | null;
  view: string | null;
  userAnswer: string | null;
  modelScore: Score;
  userScore: Score;
  direction: OverrideDirection;
  feedbackSummary: string | null;
  correctElements: string[];
  missingOrWrong: string[];
  sourceQuote: string | null;
  evaluationJson: string;
  modelId: string | null;
  promptVersion: string | null;
  markedAt: string;
  overriddenAt: string;
}

interface OverrideRow {
  id: string;
  attempt_id: string;
  user_id: string;
  question_id: string;
  document_id: string | null;
  document_title: string | null;
  section: string | null;
  category: string | null;
  citation: string | null;
  question_origin: string | null;
  question_text: string | null;
  source_text: string | null;
  view: string | null;
  user_answer: string | null;
  model_score: Score;
  user_score: Score;
  direction: OverrideDirection;
  evaluation_json: string;
  model_id: string | null;
  prompt_version: string | null;
  marked_at: number;
  updated_at: number;
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

function toRecord(row: OverrideRow): OverrideRecord {
  let evaluation: Record<string, unknown> = {};
  try {
    const parsed = JSON.parse(row.evaluation_json) as unknown;
    if (parsed && typeof parsed === "object") evaluation = parsed as Record<string, unknown>;
  } catch {
    evaluation = {};
  }
  return {
    id: row.id,
    attemptId: row.attempt_id,
    userId: row.user_id,
    questionId: row.question_id,
    documentId: row.document_id,
    documentTitle: row.document_title,
    section: row.section,
    category: row.category,
    citation: row.citation,
    questionOrigin: row.question_origin,
    questionText: row.question_text,
    sourceText: row.source_text,
    view: row.view,
    userAnswer: row.user_answer,
    modelScore: row.model_score,
    userScore: row.user_score,
    direction: row.direction,
    feedbackSummary: typeof evaluation.feedbackSummary === "string" ? evaluation.feedbackSummary : null,
    correctElements: strings(evaluation.correctElements),
    missingOrWrong: strings(evaluation.missingOrWrong),
    sourceQuote: typeof evaluation.sourceQuote === "string" ? evaluation.sourceQuote : null,
    evaluationJson: row.evaluation_json,
    modelId: row.model_id,
    promptVersion: row.prompt_version,
    markedAt: new Date(row.marked_at).toISOString(),
    overriddenAt: new Date(row.updated_at).toISOString(),
  };
}

export async function listOverrides(db: D1Database, since: number, limit: number): Promise<OverrideRecord[]> {
  const { results } = await db
    .prepare(`SELECT * FROM marking_overrides WHERE updated_at >= ?1 ORDER BY updated_at ASC LIMIT ?2`)
    .bind(since, limit)
    .all<OverrideRow>();
  return results.map(toRecord);
}

export async function overrideSummary(db: D1Database): Promise<{ total: number; modelTooHarsh: number; modelTooLenient: number }> {
  const row = await db
    .prepare(
      `SELECT COUNT(*) AS total, COALESCE(SUM(direction = 'model_too_harsh'), 0) AS harsh,
         COALESCE(SUM(direction = 'model_too_lenient'), 0) AS lenient FROM marking_overrides`,
    )
    .first<{ total: number; harsh: number; lenient: number }>();
  return { total: row?.total ?? 0, modelTooHarsh: row?.harsh ?? 0, modelTooLenient: row?.lenient ?? 0 };
}

const CSV_COLUMNS: (keyof OverrideRecord)[] = [
  "overriddenAt",
  "markedAt",
  "direction",
  "modelScore",
  "userScore",
  "questionId",
  "questionOrigin",
  "documentId",
  "documentTitle",
  "section",
  "category",
  "citation",
  "view",
  "questionText",
  "userAnswer",
  "feedbackSummary",
  "correctElements",
  "missingOrWrong",
  "sourceQuote",
  "sourceText",
  "modelId",
  "promptVersion",
  "userId",
  "attemptId",
  "id",
];

function csvCell(value: unknown): string {
  const text = Array.isArray(value) ? value.join(" | ") : value === null || value === undefined ? "" : String(value);
  const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
  return /[",\r\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function overridesCsv(records: OverrideRecord[]): string {
  const lines = [CSV_COLUMNS.join(",")];
  for (const record of records) lines.push(CSV_COLUMNS.map((key) => csvCell(record[key])).join(","));
  return `${lines.join("\r\n")}\r\n`;
}
