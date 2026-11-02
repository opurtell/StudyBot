import { Hono } from "hono";
import type { Context } from "hono";
import { CORPUS_SERVICE, parseView, VIEWS, type CorpusView } from "../corpus/repo";
import { sha256Hex } from "../lib/crypto";
import { apiError } from "../lib/http";
import type { AppEnv, SessionUser } from "../types";
import { summariseProgress, type ProgressRow, type Score, type Topic, type TopicDocument } from "../../shared/progress";

const SCORES: readonly Score[] = ["correct", "partial", "incorrect"];
const MAX_PROGRESS_ROWS = 20_000;
const HISTORY_PAGE = 20;
const MAX_IMPORT = 200;
const IMPORT_MAX_AGE_MS = 2 * 365 * 86_400_000;
const ID_PATTERN = /^[a-f0-9]{16}$/;

export function isScore(value: unknown): value is Score {
  return typeof value === "string" && (SCORES as readonly string[]).includes(value);
}

function tzOffset(raw: string | undefined): number {
  const n = Number.parseInt(raw ?? "", 10);
  return Number.isFinite(n) && Math.abs(n) <= 14 * 60 ? n : 0;
}

const TOPIC_CACHE_MS = 5 * 60 * 1000;
const topicCache = new Map<CorpusView, { at: number; topics: Promise<Topic[]> }>();

export function cachedTopics(env: Pick<Env, "DB" | "ENVIRONMENT">, view: CorpusView, now = Date.now()): Promise<Topic[]> {
  if (env.ENVIRONMENT === "development") return loadTopics(env.DB, view);
  const hit = topicCache.get(view);
  if (hit && now - hit.at < TOPIC_CACHE_MS) return hit.topics;
  const topics = loadTopics(env.DB, view);
  topicCache.set(view, { at: now, topics });
  topics.catch(() => topicCache.delete(view));
  return topics;
}

export async function loadTopics(db: D1Database, view: CorpusView): Promise<Topic[]> {
  if (!(VIEWS as readonly string[]).includes(view)) throw new Error(`bad view ${view}`);
  const vis = `vis_${view}`;
  const { results } = await db
    .prepare(
      `SELECT d.id, d.kind, d.number, d.title, d.section, COUNT(q.id) AS questions
       FROM corpus_documents d
       JOIN question_bank q ON q.document_id = d.id AND q.status = 'active' AND q.${vis} = 1
       JOIN corpus_chunks c ON c.id = q.chunk_id AND c.retired_at IS NULL AND c.embed_text = q.source_text AND c.${vis} = 1
       WHERE d.service = ?1
       GROUP BY d.id
       ORDER BY d.section, d.kind, d.number`,
    )
    .bind(CORPUS_SERVICE)
    .all<{ id: string; kind: TopicDocument["kind"]; number: string; title: string; section: string; questions: number }>();
  const bySection = new Map<string, Topic>();
  for (const r of results) {
    const topic = bySection.get(r.section) ?? { section: r.section, questions: 0, documents: [] };
    topic.questions += r.questions;
    topic.documents.push({ id: r.id, kind: r.kind, number: r.number, title: r.title, questions: r.questions });
    bySection.set(r.section, topic);
  }
  return [...bySection.values()];
}

async function progressRows(db: D1Database, userId: string): Promise<ProgressRow[]> {
  const { results } = await db
    .prepare(
      `SELECT a.question_id, q.document_id, d.title, d.section, a.score, a.created_at
       FROM attempts a
       JOIN question_bank q ON q.id = a.question_id
       JOIN corpus_documents d ON d.id = q.document_id
       WHERE a.user_id = ?1
       ORDER BY a.created_at DESC
       LIMIT ?2`,
    )
    .bind(userId, MAX_PROGRESS_ROWS)
    .all<{ question_id: string; document_id: string; title: string; section: string; score: Score | null; created_at: number }>();
  return results.map((r) => ({
    questionId: r.question_id,
    documentId: r.document_id,
    documentTitle: r.title,
    section: r.section,
    score: r.score,
    at: r.created_at,
  }));
}

export interface HistoryItem {
  id: string;
  questionId: string;
  questionText: string;
  documentId: string;
  documentTitle: string;
  section: string;
  kind: "marked" | "revealed";
  score: Score | null;
  at: number;
}

async function history(db: D1Database, userId: string, before: number | null, limit: number): Promise<HistoryItem[]> {
  const { results } = await db
    .prepare(
      `SELECT a.id, a.question_id, q.question_text, q.document_id, d.title, d.section, a.kind, a.score, a.created_at
       FROM attempts a
       JOIN question_bank q ON q.id = a.question_id
       JOIN corpus_documents d ON d.id = q.document_id
       WHERE a.user_id = ?1 AND (?2 IS NULL OR a.created_at < ?2)
       ORDER BY a.created_at DESC
       LIMIT ?3`,
    )
    .bind(userId, before, limit)
    .all<{
      id: string;
      question_id: string;
      question_text: string;
      document_id: string;
      title: string;
      section: string;
      kind: HistoryItem["kind"];
      score: Score | null;
      created_at: number;
    }>();
  return results.map((r) => ({
    id: r.id,
    questionId: r.question_id,
    questionText: r.question_text,
    documentId: r.document_id,
    documentTitle: r.title,
    section: r.section,
    kind: r.kind,
    score: r.score,
    at: r.created_at,
  }));
}

function requireUser(c: Context<AppEnv>): SessionUser | null {
  return c.get("user");
}

export const topicRoutes = new Hono<AppEnv>();

topicRoutes.get("/", async (c) => {
  const view = parseView(c.req.query("view"));
  if (!view) return apiError(c, 400, "bad_request", "Unknown view. Use ap, ap_pacer, icp or icp_pacer.");
  c.header("Cache-Control", "public, max-age=300");
  return c.json({ view, topics: await cachedTopics(c.env, view) });
});

export const progressRoutes = new Hono<AppEnv>();

progressRoutes.use("*", async (c, next) => {
  if (!requireUser(c)) return apiError(c, 401, "unauthorised", "Sign in to keep your progress on your account.");
  await next();
});

progressRoutes.get("/", async (c) => {
  const user = requireUser(c)!;
  const view = parseView(c.req.query("view"));
  if (!view) return apiError(c, 400, "bad_request", "Unknown view.");
  const [rows, topics, recent] = await Promise.all([
    progressRows(c.env.DB, user.id),
    cachedTopics(c.env, view),
    history(c.env.DB, user.id, null, 5),
  ]);
  const summary = summariseProgress(rows, topics, { now: Date.now(), tzOffsetMinutes: tzOffset(c.req.query("tz")) });
  return c.json({ ...summary, recent });
});

progressRoutes.get("/history", async (c) => {
  const user = requireUser(c)!;
  const beforeRaw = c.req.query("before");
  const before = beforeRaw ? Number.parseInt(beforeRaw, 10) : null;
  if (before !== null && !Number.isFinite(before)) return apiError(c, 400, "bad_request", "before must be a timestamp.");
  const items = await history(c.env.DB, user.id, before, HISTORY_PAGE + 1);
  return c.json({ items: items.slice(0, HISTORY_PAGE), more: items.length > HISTORY_PAGE });
});

progressRoutes.get("/attempts/:id", async (c) => {
  const user = requireUser(c)!;
  const row = await c.env.DB.prepare(
    `SELECT a.id, a.kind, a.score, a.user_answer, a.evaluation_json, a.elapsed_ms, a.created_at,
       q.id AS question_id, q.question_text, q.difficulty, q.source_citation, q.source_text, q.attribution, q.status,
       q.document_id, d.title, d.number, d.section
     FROM attempts a
     JOIN question_bank q ON q.id = a.question_id
     JOIN corpus_documents d ON d.id = q.document_id
     WHERE a.id = ?1 AND a.user_id = ?2`,
  )
    .bind(c.req.param("id"), user.id)
    .first<{
      id: string;
      kind: "marked" | "revealed";
      score: Score | null;
      user_answer: string | null;
      evaluation_json: string | null;
      elapsed_ms: number | null;
      created_at: number;
      question_id: string;
      question_text: string;
      difficulty: string;
      source_citation: string;
      source_text: string;
      attribution: string;
      status: string;
      document_id: string;
      title: string;
      number: string;
      section: string;
    }>();
  if (!row) return apiError(c, 404, "not_found", "No such answer in your history.");
  let evaluation: Record<string, unknown> | null = null;
  try {
    evaluation = row.evaluation_json ? (JSON.parse(row.evaluation_json) as Record<string, unknown>) : null;
  } catch {
    evaluation = null;
  }
  return c.json({
    id: row.id,
    kind: row.kind,
    score: row.score,
    answer: row.user_answer,
    elapsedMs: row.elapsed_ms,
    at: row.created_at,
    evaluation,
    question: {
      id: row.question_id,
      text: row.question_text,
      difficulty: row.difficulty,
      withdrawn: row.status !== "active",
    },
    sourceText: row.source_text,
    citation: row.source_citation,
    documentId: row.document_id,
    documentTitle: row.title,
    section: row.section,
    attribution: row.attribution,
  });
});

progressRoutes.delete("/", async (c) => {
  const user = requireUser(c)!;
  await c.env.DB.batch([
    c.env.DB.prepare(`DELETE FROM attempts WHERE user_id = ?1`).bind(user.id),
    c.env.DB.prepare(`DELETE FROM user_question_seen WHERE user_id = ?1`).bind(user.id),
  ]);
  c.get("log").info("progress_reset", { userId: user.id });
  return c.json({ ok: true });
});

progressRoutes.post("/import", async (c) => {
  const user = requireUser(c)!;
  const body = await c.req.json<unknown>().catch(() => null);
  const raw = body && typeof body === "object" && !Array.isArray(body) ? (body as Record<string, unknown>).attempts : null;
  if (!Array.isArray(raw) || raw.length > MAX_IMPORT) {
    return apiError(c, 400, "bad_request", `Send up to ${MAX_IMPORT} attempts at a time.`);
  }
  const now = Date.now();
  const valid: { questionId: string; score: Score | null; at: number }[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const { questionId, score, at } = item as Record<string, unknown>;
    if (typeof questionId !== "string" || !ID_PATTERN.test(questionId)) continue;
    if (score !== null && !isScore(score)) continue;
    if (typeof at !== "number" || !Number.isInteger(at) || at > now + 60_000 || at < now - IMPORT_MAX_AGE_MS) continue;
    valid.push({ questionId, score, at: Math.min(at, now) });
  }
  if (valid.length === 0) return c.json({ imported: 0, skipped: raw.length });

  const db = c.env.DB;
  const stmts: D1PreparedStatement[] = [];
  for (const a of valid) {
    const id = `import-${(await sha256Hex(`${user.id}:${a.questionId}:${a.at}`)).slice(0, 32)}`;
    stmts.push(
      db
        .prepare(
          `INSERT INTO attempts (id, user_id, question_id, kind, score, created_at)
           SELECT ?1, ?2, ?3, 'revealed', ?4, ?5 WHERE EXISTS (SELECT 1 FROM question_bank WHERE id = ?3)
           ON CONFLICT (id) DO NOTHING`,
        )
        .bind(id, user.id, a.questionId, a.score, a.at),
      db
        .prepare(
          `INSERT INTO user_question_seen (user_id, question_id, first_seen_at, last_seen_at)
           SELECT ?1, ?2, ?3, ?3 WHERE EXISTS (SELECT 1 FROM question_bank WHERE id = ?2)
           ON CONFLICT (user_id, question_id) DO UPDATE SET
             first_seen_at = MIN(first_seen_at, excluded.first_seen_at),
             last_seen_at = MAX(last_seen_at, excluded.last_seen_at)`,
        )
        .bind(user.id, a.questionId, a.at),
    );
  }
  const results = await db.batch(stmts);
  const imported = results.filter((_, i) => i % 2 === 0).reduce((n, r) => n + (r.meta.changes ?? 0), 0);
  c.get("log").info("progress_imported", { userId: user.id, imported, sent: raw.length });
  return c.json({ imported, skipped: raw.length - imported });
});
