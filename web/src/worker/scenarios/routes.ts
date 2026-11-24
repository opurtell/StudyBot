import { Hono } from "hono";
import type { Context } from "hono";
import { parseView, type CorpusView } from "../corpus/repo";
import { sha256Hex } from "../lib/crypto";
import { apiError, clientIp } from "../lib/http";
import { REPORT_REASONS } from "../quiz/bank";
import { apViewFor } from "../quiz/scope";
import { startOfUtcDay } from "../quiz/usage";
import type { AppEnv } from "../types";
import { scenarioScore, stageScore, type Score } from "../../shared/scenarios";
import {
  adminSummary,
  DIFFICULTIES,
  getScenario,
  insertAttempt,
  isPatientGroup,
  nextScenario,
  parseStages,
  publicRubric,
  publicStage,
  recordSeen,
  reportScenario,
  reportsToday,
  scenarioAudience,
  scenarioExists,
  scenarioOptions,
  setScenarioAudience,
  setScenarioStatus,
  type Difficulty,
  type ScenarioFilters,
  type ScenarioRow,
} from "./bank";

const ID_PATTERN = /^[a-f0-9]{16}$/;
const MAX_EXCLUDE = 400;
const MAX_ANSWER_CHARS = 4000;
const MAX_DETAIL_CHARS = 1000;
const MAX_REPORTS_PER_DAY = 20;

type Body = Record<string, unknown>;

async function readBody(c: Context<AppEnv>): Promise<Body | null> {
  const body = await c.req.json<unknown>().catch(() => null);
  return body && typeof body === "object" && !Array.isArray(body) ? (body as Body) : null;
}

function viewOf(value: unknown): CorpusView | null {
  return value === undefined || typeof value === "string" ? parseView(value as string | undefined) : null;
}

function parseFilters(body: Body, view: CorpusView): ScenarioFilters | null {
  const category = body.category ?? null;
  const difficulty = body.difficulty ?? null;
  const patientGroup = body.patientGroup ?? null;
  if (category !== null && (typeof category !== "string" || category.length === 0 || category.length > 100)) return null;
  if (difficulty !== null && !(DIFFICULTIES as readonly unknown[]).includes(difficulty)) return null;
  if (patientGroup !== null && !isPatientGroup(patientGroup)) return null;
  if (body.icpOnly !== undefined && typeof body.icpOnly !== "boolean") return null;
  const icpOnly = body.icpOnly === true;
  if (icpOnly && !apViewFor(view)) return null;
  return { category: category as string | null, difficulty: difficulty as Difficulty | null, patientGroup, icpOnly };
}

function summary(row: ScenarioRow) {
  const stages = parseStages(row.stages_json);
  return {
    id: row.id,
    title: row.title,
    dispatch: row.dispatch_text,
    category: row.category,
    difficulty: row.difficulty,
    patientGroup: row.patient_group,
    documentId: row.primary_document_id,
    documentTitle: row.document_title,
    stageCount: stages.length,
    stage: stages[0] ? publicStage(stages[0]) : null,
  };
}

function reportThreshold(env: Env): number {
  const n = Number.parseInt(env.REPORT_FLAG_THRESHOLD ?? "", 10);
  return Number.isFinite(n) && n >= 1 ? n : 2;
}

export const scenarioRoutes = new Hono<AppEnv>();

scenarioRoutes.use("*", async (c, next) => {
  if ((await scenarioAudience(c.env.DB)) !== "everyone" && !c.get("user")?.isAdmin) {
    return apiError(c, 404, "not_found", "Not found.");
  }
  await next();
});

scenarioRoutes.get("/options", async (c) => {
  const view = viewOf(c.req.query("view"));
  const icpOnly = c.req.query("icpOnly") === "true";
  if (!view || (icpOnly && !apViewFor(view))) return apiError(c, 400, "bad_request", "Unknown scope.");
  return c.json({ options: await scenarioOptions(c.env.DB, view, icpOnly) });
});

scenarioRoutes.post("/next", async (c) => {
  const body = await readBody(c);
  if (!body) return apiError(c, 400, "bad_request", "Send a JSON object.");
  const view = viewOf(body.view);
  const filters = view ? parseFilters(body, view) : null;
  if (!view || !filters) return apiError(c, 400, "bad_request", "Unknown scope, category, difficulty or patient group.");
  const exclude = Array.isArray(body.exclude) ? body.exclude.filter((x): x is string => typeof x === "string" && ID_PATTERN.test(x)) : [];
  if (exclude.length > MAX_EXCLUDE) return apiError(c, 400, "bad_request", "Too many seen scenarios.");
  const user = c.get("user");
  const repeat = body.repeat === true;
  const row = await nextScenario(c.env.DB, { view, filters, userId: user?.id ?? null, exclude, repeat });
  if (!row) {
    const anySeen = repeat ? null : await nextScenario(c.env.DB, { view, filters, userId: user?.id ?? null, exclude: [], repeat: true });
    return c.json({ scenario: null, exhausted: true, canRepeat: Boolean(anySeen) });
  }
  await recordSeen(c.env.DB, row.id, user?.id ?? null, Date.now());
  return c.json({ scenario: summary(row), exhausted: false });
});

scenarioRoutes.post("/:id/stages/:n/reveal", async (c) => {
  const body = await readBody(c);
  const view = body ? viewOf(body.view) : null;
  if (!view) return apiError(c, 400, "bad_request", "Unknown scope.");
  const row = await getScenario(c.env.DB, c.req.param("id"), view);
  if (!row) return apiError(c, 404, "not_found", "No such scenario in this scope.");
  const stages = parseStages(row.stages_json);
  const n = Number.parseInt(c.req.param("n"), 10);
  const stage = stages.find((s) => s.ordinal === n);
  if (!stage) return apiError(c, 404, "not_found", "No such stage.");
  const following = stages.find((s) => s.ordinal === n + 1);
  return c.json({
    ordinal: stage.ordinal,
    rubric: publicRubric(stage),
    next: following ? publicStage(following) : null,
  });
});

scenarioRoutes.post("/:id/attempts", async (c) => {
  const user = c.get("user");
  if (!user) return apiError(c, 401, "unauthorised", "Sign in to save scenario results.");
  const body = await readBody(c);
  const view = body ? viewOf(body.view) : null;
  if (!body || !view || !Array.isArray(body.stages)) return apiError(c, 400, "bad_request", "Send the scope and each stage's ticks.");
  const row = await getScenario(c.env.DB, c.req.param("id"), view);
  if (!row) return apiError(c, 404, "not_found", "No such scenario in this scope.");
  const stages = parseStages(row.stages_json);
  const sent = new Map<number, { ticked: number[]; answer: string | null }>();
  for (const item of body.stages as unknown[]) {
    if (!item || typeof item !== "object") return apiError(c, 400, "bad_request", "Bad stage result.");
    const { ordinal, ticked, answer } = item as Record<string, unknown>;
    const stage = stages.find((s) => s.ordinal === ordinal);
    if (!stage || !Array.isArray(ticked) || ticked.some((t) => !Number.isInteger(t) || (t as number) < 0 || (t as number) >= stage.rubric.length)) {
      return apiError(c, 400, "bad_request", "Bad stage result.");
    }
    sent.set(stage.ordinal, {
      ticked: [...new Set(ticked as number[])],
      answer: typeof answer === "string" && answer.trim() ? answer.trim().slice(0, MAX_ANSWER_CHARS) : null,
    });
  }
  if (sent.size !== stages.length) return apiError(c, 400, "bad_request", "Send a result for every stage.");
  const results = stages.map((s) => {
    const r = sent.get(s.ordinal)!;
    return { ordinal: s.ordinal, ticked: r.ticked, answer: r.answer, score: stageScore(s.rubric, r.ticked) as Score };
  });
  const score = scenarioScore(results.map((r) => r.score));
  const attemptId = await insertAttempt(c.env.DB, { userId: user.id, scenarioId: row.id, view, stages: results, score }, Date.now());
  return c.json({ attemptId, score, stages: results.map(({ ordinal, score: s }) => ({ ordinal, score: s })) });
});

scenarioRoutes.post("/:id/report", async (c) => {
  const id = c.req.param("id");
  const body = await readBody(c);
  if (!body) return apiError(c, 400, "bad_request", "Send a JSON object.");
  const reason = body.reason;
  if (typeof reason !== "string" || !(REPORT_REASONS as readonly string[]).includes(reason)) {
    return apiError(c, 400, "bad_request", "Choose a reason.");
  }
  const stage = body.stage === undefined || body.stage === null ? null : body.stage;
  if (stage !== null && (!Number.isInteger(stage) || (stage as number) < 1 || (stage as number) > 10)) {
    return apiError(c, 400, "bad_request", "Unknown stage.");
  }
  const detail = body.detail === undefined || body.detail === null ? null : body.detail;
  if (detail !== null && (typeof detail !== "string" || detail.length > MAX_DETAIL_CHARS)) {
    return apiError(c, 400, "bad_request", `Keep details under ${MAX_DETAIL_CHARS} characters.`);
  }
  if (!ID_PATTERN.test(id) || !(await scenarioExists(c.env.DB, id))) return apiError(c, 404, "not_found", "No such scenario.");
  const user = c.get("user");
  const reporterKey = user ? `user:${user.id}` : `ip:${await sha256Hex(`report:${clientIp(c)}`)}`;
  if (!user?.isAdmin && (await reportsToday(c.env.DB, reporterKey, startOfUtcDay(Date.now()))) >= MAX_REPORTS_PER_DAY) {
    return apiError(c, 429, "rate_limited", "You've sent a lot of reports today. Thanks — try again tomorrow.");
  }
  const { flagged } = await reportScenario(
    c.env.DB,
    {
      scenarioId: id,
      stage: stage as number | null,
      userId: user?.id ?? null,
      reporterKey,
      reason,
      detail: (detail as string | null)?.trim() || null,
      flagNow: Boolean(user?.isAdmin),
      threshold: reportThreshold(c.env),
    },
    Date.now(),
  );
  c.get("log").info("scenario_reported", { scenarioId: id, reason, flagged });
  return c.json({ ok: true, withdrawn: flagged });
});

export const adminScenarioRoutes = new Hono<AppEnv>();

adminScenarioRoutes.use("*", async (c, next) => {
  const user = c.get("user");
  if (!user) return apiError(c, 401, "unauthorised", "Sign in first.");
  if (!user.isAdmin) return apiError(c, 403, "forbidden", "Admins only.");
  await next();
});

adminScenarioRoutes.get("/", async (c) => {
  const [summaryData, audience] = await Promise.all([adminSummary(c.env.DB), scenarioAudience(c.env.DB)]);
  return c.json({ ...summaryData, audience });
});

adminScenarioRoutes.post("/audience", async (c) => {
  const body = await readBody(c);
  const audience = body?.audience;
  if (audience !== "admins" && audience !== "everyone") return apiError(c, 400, "bad_request", "Audience is admins or everyone.");
  await setScenarioAudience(c.env.DB, audience, Date.now());
  c.get("log").info("scenarios_audience", { audience, userId: c.get("user")?.id ?? null });
  return c.json({ audience });
});

adminScenarioRoutes.post("/:id/status", async (c) => {
  const body = await readBody(c);
  const status = body?.status;
  if (status !== "active" && status !== "retired") return apiError(c, 400, "bad_request", "Status is active or retired.");
  const ok = await setScenarioStatus(c.env.DB, c.req.param("id"), status, Date.now());
  if (!ok) return apiError(c, 404, "not_found", "No such scenario.");
  c.get("log").info("scenario_status", { scenarioId: c.req.param("id"), status });
  return c.json({ ok: true, status });
});
