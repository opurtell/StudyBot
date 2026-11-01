import { Hono } from "hono";
import type { Context } from "hono";
import { currentCorpusVersion, parseView, type CorpusView } from "../corpus/repo";
import { complete, LlmError, MODELS, type LlmResult } from "../llm/gemini";
import { sha256Hex } from "../lib/crypto";
import { apiError, clientIp } from "../lib/http";
import { summariseQuota } from "../lib/quota";
import type { AppEnv } from "../types";
import {
  bankSummary,
  candidateChunks,
  findByHash,
  getQuestion,
  insertLiveQuestion,
  nextQuestion,
  previousQuestionsFor,
  questionExists,
  questionHash,
  recordServed,
  REPORT_REASONS,
  reportedQuestions,
  reportQuestion,
  retireStaleQuestions,
  setQuestionStatus,
  type QuestionFilters,
  type ReportReason,
} from "./bank";
import {
  DIFFICULTIES,
  EVALUATION_SCHEMA,
  EVALUATION_SYSTEM,
  generationSystem,
  generationUser,
  GENERATION_SCHEMA,
  markingUser,
  parseEvaluation,
  parseGeneration,
  PROMPT_VERSION,
  type Difficulty,
} from "./prompts";
import { questionVisibility } from "./scope";
import {
  dailyCaps,
  ledgerStatement,
  liveAiAvailability,
  liveAiEnabled,
  readQuota,
  refundCredit,
  setLiveAi,
  takeCredit,
  usedToday,
  type Availability,
  type CreditKind,
} from "./usage";

const MAX_ANSWER_CHARS = 4000;
const MAX_DETAIL_CHARS = 1000;
const MAX_EXCLUDE = 400;
const ID_PATTERN = /^[a-f0-9]{16}$/;

export const UNREADABLE_MARK_MESSAGE =
  "The marking model returned an unreadable response, so your answer was not scored. Please try again.";

type Body = Record<string, unknown>;

async function readBody(c: Context<AppEnv>): Promise<Body | null> {
  const body = await c.req.json<unknown>().catch(() => null);
  return body && typeof body === "object" && !Array.isArray(body) ? (body as Body) : null;
}

function optionalString(value: unknown, max = 200): string | null | undefined {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value !== "string" || value.length > max) return undefined;
  return value;
}

function parseFilters(body: Body): QuestionFilters | null {
  const documentId = optionalString(body.documentId);
  const section = optionalString(body.section);
  const difficulty = optionalString(body.difficulty, 10);
  if (documentId === undefined || section === undefined || difficulty === undefined) return null;
  if (difficulty !== null && !(DIFFICULTIES as readonly string[]).includes(difficulty)) return null;
  return { documentId, section, difficulty: difficulty as Difficulty | null };
}

function viewFrom(body: Body): CorpusView | null {
  return typeof body.view === "string" || body.view === undefined ? parseView(body.view as string | undefined) : null;
}

async function quotaFor(c: Context<AppEnv>) {
  const user = c.get("user");
  if (!user) return null;
  return summariseQuota(c.env, await readQuota(c.env.DB, user.id));
}

function unavailableMessage(kind: CreditKind, availability: Exclude<Availability, { ok: true }>): string {
  const what = kind === "eval" ? "AI marking" : "Generating new questions";
  if (availability.reason === "daily_cap") return `${what} has reached today's limit for the site. Try again tomorrow.`;
  return `${what} is switched off at the moment.`;
}

function llmFailure(c: Context<AppEnv>, err: LlmError, kind: CreditKind) {
  const what = kind === "eval" ? "AI marking" : "Generating new questions";
  if (err.kind === "spend_limit" || err.kind === "config") {
    return apiError(c, 503, "unavailable", `${what} is switched off at the moment. Nothing was taken from your allowance.`);
  }
  if (err.kind === "rate_limited") {
    return apiError(c, 503, "unavailable", `${what} is busy. Wait a moment and try again. Nothing was taken from your allowance.`);
  }
  return apiError(c, 502, "upstream_error", `${what} didn't respond properly. Nothing was taken from your allowance. Try again.`);
}

export const quizRoutes = new Hono<AppEnv>();

quizRoutes.post("/next", async (c) => {
  const body = await readBody(c);
  if (!body) return apiError(c, 400, "bad_request", "Send a JSON object.");
  const view = viewFrom(body);
  const filters = parseFilters(body);
  if (!view || !filters) return apiError(c, 400, "bad_request", "Unknown scope, guideline or difficulty.");
  const rawExclude = body.exclude ?? [];
  if (!Array.isArray(rawExclude) || rawExclude.some((id) => typeof id !== "string" || !ID_PATTERN.test(id))) {
    return apiError(c, 400, "bad_request", "exclude must be a list of question ids.");
  }
  const exclude = (rawExclude as string[]).slice(-MAX_EXCLUDE);
  const user = c.get("user");
  const now = Date.now();
  const repeat = body.repeat === true;

  const question = await nextQuestion(c.env.DB, { view, filters, userId: user?.id ?? null, exclude, repeat });
  if (question) await recordServed(c.env.DB, question.id, user?.id ?? null, now);
  const quota = await quotaFor(c);
  const live = user ? await liveAiAvailability(c.env, "gen", now) : null;
  return c.json({
    question,
    exhausted: question === null,
    canGenerate: Boolean(user && live?.ok && quota && quota.generations.remaining > 0),
    quota,
  });
});

quizRoutes.post("/generate", async (c) => {
  const user = c.get("user");
  if (!user) return apiError(c, 401, "unauthorised", "Sign in to generate new questions.");
  const body = await readBody(c);
  if (!body) return apiError(c, 400, "bad_request", "Send a JSON object.");
  const view = viewFrom(body);
  const filters = parseFilters(body);
  if (!view || !filters) return apiError(c, 400, "bad_request", "Unknown scope, guideline or difficulty.");
  const difficulty: Difficulty = filters.difficulty ?? "medium";
  const now = Date.now();
  const log = c.get("log");

  const availability = await liveAiAvailability(c.env, "gen", now);
  if (!availability.ok) return apiError(c, 503, "unavailable", unavailableMessage("gen", availability));

  const chunks = await candidateChunks(c.env.DB, view, filters);
  if (chunks.length === 0) return apiError(c, 404, "not_found", "There's no guideline text in this scope to write a question from.");

  if (!(await takeCredit(c.env.DB, c.env, user.id, "gen", new Date(now)))) {
    return apiError(c, 429, "quota_exhausted", "You've used this month's new questions. Library questions are still unlimited.");
  }

  let result: LlmResult;
  try {
    result = await complete(c.env, {
      role: "generation",
      system: generationSystem(view),
      user: generationUser(
        chunks.map((ch) => ch.embedText),
        difficulty,
        await previousQuestionsFor(
          c.env.DB,
          chunks.map((ch) => ch.id),
        ),
      ),
      maxOutputTokens: 2048,
      responseSchema: GENERATION_SCHEMA,
      metadata: { kind: "gen", user: user.id, prompt: PROMPT_VERSION },
    });
  } catch (err) {
    await refundCredit(c.env.DB, user.id, "gen", new Date(now));
    await ledgerStatement(c.env.DB, { userId: user.id, kind: "gen", outcome: "error", modelId: MODELS.generation, now }).run();
    if (err instanceof LlmError) {
      log.warn("generation_failed", { kind: err.kind, status: err.status ?? null, model: MODELS.generation });
      return llmFailure(c, err, "gen");
    }
    throw err;
  }

  const parsed = parseGeneration(result.text, chunks.length);
  if (!parsed) {
    await refundCredit(c.env.DB, user.id, "gen", new Date(now));
    await ledgerStatement(c.env.DB, { userId: user.id, kind: "gen", outcome: "unreadable", modelId: result.modelId, result, now }).run();
    log.warn("generation_unreadable", { model: result.modelId, promptVersion: PROMPT_VERSION, finishReason: result.finishReason });
    return apiError(c, 502, "unreadable_response", "The question model returned an unreadable response. Nothing was taken from your allowance. Try again.");
  }

  const chunk = chunks[parsed.sourceIndex] ?? chunks[0]!;
  const hash = await questionHash(parsed.questionText);
  const existing = await findByHash(c.env.DB, hash);
  let questionId = existing?.id ?? null;
  let duplicate = existing !== null;
  if (!questionId) {
    questionId = await insertLiveQuestion(
      c.env.DB,
      {
        chunk,
        text: parsed.questionText,
        type: parsed.questionType,
        difficulty,
        category: parsed.category ?? chunk.section,
        citation: parsed.sourceCitation ?? chunk.documentId,
        generatedFor: view,
        visibility: questionVisibility(view, chunk.visibility, parsed.questionText),
        hash,
        modelId: result.modelId,
        promptVersion: PROMPT_VERSION,
        corpusVersion: (await currentCorpusVersion(c.env.DB)) ?? "unknown",
      },
      now,
    );
    if (!questionId) {
      questionId = (await findByHash(c.env.DB, hash))?.id ?? null;
      duplicate = true;
    }
  }
  const found = questionId ? await getQuestion(c.env.DB, questionId, view) : null;
  const question = found?.status === "active" ? found : null;
  if (duplicate || !question) await refundCredit(c.env.DB, user.id, "gen", new Date(now));
  await ledgerStatement(c.env.DB, {
    userId: user.id,
    kind: "gen",
    outcome: "ok",
    modelId: result.modelId,
    questionId,
    result,
    now,
  }).run();

  if (!question) {
    log.warn("generation_out_of_scope", { model: result.modelId, view });
    return apiError(c, 502, "unreadable_response", "The new question fell outside your scope, so it wasn't shown. Nothing was taken from your allowance. Try again.");
  }
  await recordServed(c.env.DB, question.id, user.id, now);
  const { sourceText: _s, attribution: _a, licence: _l, status: _st, ...publicQuestion } = question;
  return c.json({ question: publicQuestion, duplicate, quota: await quotaFor(c) });
});

quizRoutes.post("/questions/:id/reveal", async (c) => {
  const body = await readBody(c);
  const view = body ? viewFrom(body) : null;
  if (!view) return apiError(c, 400, "bad_request", "Unknown scope.");
  const question = await getQuestion(c.env.DB, c.req.param("id"), view);
  if (!question) return apiError(c, 404, "not_found", "No such question in this scope.");
  const user = c.get("user");
  if (user) {
    await c.env.DB.prepare(
      `INSERT INTO attempts (id, user_id, question_id, kind, created_at) VALUES (?1, ?2, ?3, 'revealed', ?4)`,
    )
      .bind(crypto.randomUUID(), user.id, question.id, Date.now())
      .run();
  }
  return c.json({
    questionId: question.id,
    score: null,
    sourceQuote: question.sourceText,
    sourceText: question.sourceText,
    citation: question.citation,
    documentId: question.documentId,
    documentTitle: question.documentTitle,
    attribution: question.attribution,
  });
});

quizRoutes.post("/questions/:id/mark", async (c) => {
  const user = c.get("user");
  if (!user) return apiError(c, 401, "unauthorised", "Sign in for AI marking, or reveal the reference to check your own answer.");
  const body = await readBody(c);
  if (!body) return apiError(c, 400, "bad_request", "Send a JSON object.");
  const view = viewFrom(body);
  if (!view) return apiError(c, 400, "bad_request", "Unknown scope.");
  const answer = typeof body.answer === "string" ? body.answer.trim() : "";
  if (!answer) return apiError(c, 400, "bad_request", "Write an answer first, or reveal the reference.");
  if (answer.length > MAX_ANSWER_CHARS) return apiError(c, 400, "bad_request", `Keep answers under ${MAX_ANSWER_CHARS} characters.`);
  const elapsedMs = typeof body.elapsedMs === "number" && body.elapsedMs >= 0 ? Math.round(body.elapsedMs) : null;

  const question = await getQuestion(c.env.DB, c.req.param("id"), view);
  if (!question) return apiError(c, 404, "not_found", "No such question in this scope.");
  if (question.status !== "active") return apiError(c, 404, "not_found", "This question has been withdrawn for review.");

  const now = Date.now();
  const log = c.get("log");
  const availability = await liveAiAvailability(c.env, "eval", now);
  if (!availability.ok) return apiError(c, 503, "unavailable", `${unavailableMessage("eval", availability)} Reveal the reference to check your own answer.`);
  if (!(await takeCredit(c.env.DB, c.env, user.id, "eval", new Date(now)))) {
    return apiError(c, 429, "quota_exhausted", "You've used this month's AI marking. Reveal the reference to check your own answer.");
  }

  let result: LlmResult;
  try {
    result = await complete(c.env, {
      role: "marking",
      system: EVALUATION_SYSTEM,
      user: markingUser(question.text, question.sourceText, answer),
      maxOutputTokens: 2048,
      responseSchema: c.env.MARKING_SCHEMA === "on" ? EVALUATION_SCHEMA : undefined,
      metadata: { kind: "eval", user: user.id, prompt: PROMPT_VERSION },
    });
  } catch (err) {
    await refundCredit(c.env.DB, user.id, "eval", new Date(now));
    await ledgerStatement(c.env.DB, { userId: user.id, kind: "eval", outcome: "error", modelId: MODELS.marking, questionId: question.id, now }).run();
    if (err instanceof LlmError) {
      log.warn("marking_failed", { kind: err.kind, status: err.status ?? null, model: MODELS.marking });
      return llmFailure(c, err, "eval");
    }
    throw err;
  }

  const evaluation = parseEvaluation(result.text);
  if (!evaluation) {
    await refundCredit(c.env.DB, user.id, "eval", new Date(now));
    await ledgerStatement(c.env.DB, { userId: user.id, kind: "eval", outcome: "unreadable", modelId: result.modelId, questionId: question.id, result, now }).run();
    log.warn("marking_unreadable", { model: result.modelId, promptVersion: PROMPT_VERSION, finishReason: result.finishReason });
    return apiError(c, 502, "unreadable_response", UNREADABLE_MARK_MESSAGE);
  }

  await c.env.DB.batch([
    ledgerStatement(c.env.DB, { userId: user.id, kind: "eval", outcome: "ok", modelId: result.modelId, questionId: question.id, result, now }),
    c.env.DB.prepare(
      `INSERT INTO attempts (id, user_id, question_id, kind, score, user_answer, evaluation_json, elapsed_ms, prompt_version, model_id, created_at)
       VALUES (?1, ?2, ?3, 'marked', ?4, ?5, ?6, ?7, ?8, ?9, ?10)`,
    ).bind(
      crypto.randomUUID(),
      user.id,
      question.id,
      evaluation.score,
      answer,
      JSON.stringify(evaluation),
      elapsedMs,
      PROMPT_VERSION,
      result.modelId,
      now,
    ),
  ]);

  return c.json({
    questionId: question.id,
    ...evaluation,
    sourceText: question.sourceText,
    citation: question.citation,
    documentId: question.documentId,
    documentTitle: question.documentTitle,
    attribution: question.attribution,
    quota: await quotaFor(c),
  });
});

function reportThreshold(env: Env): number {
  const n = Number.parseInt(env.REPORT_FLAG_THRESHOLD ?? "", 10);
  return Number.isFinite(n) && n >= 1 ? n : 2;
}

quizRoutes.post("/questions/:id/report", async (c) => {
  const id = c.req.param("id");
  const body = await readBody(c);
  if (!body) return apiError(c, 400, "bad_request", "Send a JSON object.");
  const reason = body.reason;
  if (typeof reason !== "string" || !(REPORT_REASONS as readonly string[]).includes(reason)) {
    return apiError(c, 400, "bad_request", "Choose a reason.");
  }
  const detail = optionalString(body.detail, MAX_DETAIL_CHARS);
  if (detail === undefined) return apiError(c, 400, "bad_request", `Keep details under ${MAX_DETAIL_CHARS} characters.`);
  if (!ID_PATTERN.test(id) || !(await questionExists(c.env.DB, id))) return apiError(c, 404, "not_found", "No such question.");
  const user = c.get("user");
  const reporterKey = user ? `user:${user.id}` : `ip:${await sha256Hex(`report:${clientIp(c)}`)}`;
  const { flagged } = await reportQuestion(
    c.env.DB,
    {
      questionId: id,
      userId: user?.id ?? null,
      reporterKey,
      reason: reason as ReportReason,
      detail: detail?.trim() || null,
      flagNow: Boolean(user?.isAdmin),
      threshold: reportThreshold(c.env),
    },
    Date.now(),
  );
  c.get("log").info("question_reported", { questionId: id, reason, flagged });
  return c.json({ ok: true, withdrawn: flagged });
});

export const adminQuestionRoutes = new Hono<AppEnv>();

adminQuestionRoutes.use("*", async (c, next) => {
  const user = c.get("user");
  if (!user) return apiError(c, 401, "unauthorised", "Sign in first.");
  if (!user.isAdmin) return apiError(c, 403, "forbidden", "Admins only.");
  await next();
});

adminQuestionRoutes.get("/", async (c) => {
  const now = Date.now();
  const db = c.env.DB;
  const [summary, reported, liveAi, gensToday, marksToday, spend] = await Promise.all([
    bankSummary(db),
    reportedQuestions(db),
    liveAiEnabled(db),
    usedToday(db, "gen", now),
    usedToday(db, "eval", now),
    db
      .prepare(
        `SELECT COALESCE(SUM(cost_usd_micros), 0) AS micros, COUNT(*) AS calls,
           COALESCE(SUM(outcome = 'unreadable'), 0) AS unreadable
         FROM usage_ledger WHERE created_at >= ?1`,
      )
      .bind(Date.UTC(new Date(now).getUTCFullYear(), new Date(now).getUTCMonth(), 1))
      .first<{ micros: number; calls: number; unreadable: number }>(),
  ]);
  return c.json({
    summary,
    reported,
    liveAi,
    today: { generations: gensToday, marks: marksToday, caps: dailyCaps(c.env) },
    month: { costUsd: (spend?.micros ?? 0) / 1_000_000, calls: spend?.calls ?? 0, unreadable: spend?.unreadable ?? 0 },
  });
});

adminQuestionRoutes.post("/live-ai", async (c) => {
  const body = await readBody(c);
  if (!body || typeof body.enabled !== "boolean") return apiError(c, 400, "bad_request", "Send { enabled: true | false }.");
  await setLiveAi(c.env.DB, body.enabled, Date.now());
  c.get("log").info("live_ai_toggled", { enabled: body.enabled, userId: c.get("user")?.id ?? null });
  return c.json({ liveAi: body.enabled });
});

adminQuestionRoutes.post("/retire-stale", async (c) => {
  const retired = await retireStaleQuestions(c.env.DB, Date.now());
  return c.json({ retired });
});

adminQuestionRoutes.post("/:id/status", async (c) => {
  const body = await readBody(c);
  const status = body?.status;
  if (status !== "active" && status !== "retired") return apiError(c, 400, "bad_request", "Status must be active or retired.");
  const ok = await setQuestionStatus(c.env.DB, c.req.param("id"), status, Date.now());
  if (!ok) return apiError(c, 404, "not_found", "No such question.");
  c.get("log").info("question_status", { questionId: c.req.param("id"), status });
  return c.json({ ok: true, status });
});
