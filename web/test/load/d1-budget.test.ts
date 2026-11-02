/// <reference types="node" />
import { AsyncLocalStorage } from "node:async_hooks";
import { env } from "cloudflare:workers";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { app } from "../../src/worker/app";
import { ORIGIN, signIn } from "../worker/helpers";

const USERS = Number(process.env.LOAD_USERS ?? 30);
const QUESTIONS_PER_USER = Number(process.env.LOAD_QUESTIONS ?? 30);
const BANK_SIZE = Number(process.env.LOAD_BANK ?? 1200);
const DOCS = 190;
const MARK_SHARE = 0.4;

const FREE_TIER = { rowsReadPerDay: 5_000_000, rowsWrittenPerDay: 100_000, requestsPerDay: 100_000 };

interface Tally {
  calls: number;
  rowsRead: number;
  rowsWritten: number;
  ms: number;
}

const tallies = new Map<string, Tally>();
const scope = new AsyncLocalStorage<Tally>();

function record(meta: { rows_read?: number; rows_written?: number } | undefined) {
  const current = scope.getStore();
  if (!current || !meta) return;
  current.rowsRead += meta.rows_read ?? 0;
  current.rowsWritten += meta.rows_written ?? 0;
}

function wrapStatement(stmt: D1PreparedStatement): D1PreparedStatement {
  return new Proxy(stmt, {
    get(target, prop, receiver) {
      if (prop === "bind") return (...args: unknown[]) => wrapStatement(target.bind(...args));
      if (prop === "first")
        return async (col?: string) => {
          const res = await target.all<Record<string, unknown>>();
          record(res.meta);
          const row = res.results[0] ?? null;
          return col ? (row?.[col] ?? null) : row;
        };
      if (prop === "all" || prop === "run")
        return async () => {
          const res = await (target[prop] as () => Promise<D1Result>)();
          record(res.meta);
          return res;
        };
      const value = Reflect.get(target, prop, receiver);
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
}

const countingDb = new Proxy(env.DB, {
  get(target, prop) {
    if (prop === "prepare") return (sql: string) => wrapStatement(target.prepare(sql));
    if (prop === "batch")
      return async (stmts: D1PreparedStatement[]) => {
        const res = await target.batch(stmts);
        for (const r of res) record(r.meta);
        return res;
      };
    const value = Reflect.get(target, prop);
    return typeof value === "function" ? value.bind(target) : value;
  },
});

async function timed(label: string, path: string, init: RequestInit & { cookie?: string } = {}) {
  const tally = tallies.get(label) ?? { calls: 0, rowsRead: 0, rowsWritten: 0, ms: 0 };
  tallies.set(label, tally);
  const headers = new Headers(init.headers);
  headers.set("cf-connecting-ip", `198.51.100.${Math.floor(Math.random() * 250)}`);
  if (init.cookie) headers.set("cookie", init.cookie);
  if (init.method && init.method !== "GET") {
    headers.set("origin", ORIGIN);
    headers.set("content-type", "application/json");
  }
  const started = performance.now();
  const res = await scope.run(tally, async () => {
    const r = await app.request(`${ORIGIN}${path}`, { ...init, headers }, { ...env, DB: countingDb, ENVIRONMENT: "load-test" });
    await r.clone().arrayBuffer();
    return r;
  });
  tally.ms += performance.now() - started;
  tally.calls += 1;
  return res;
}

const post = (label: string, path: string, body: unknown, cookie?: string) =>
  timed(label, path, { method: "POST", body: JSON.stringify(body), cookie });

async function seedBank() {
  const db = env.DB;
  for (const t of ["question_reports", "usage_ledger", "daily_usage", "attempts", "user_question_seen", "question_bank", "app_flags", "corpus_chunks", "corpus_documents", "corpus_versions"]) {
    await db.prepare(`DELETE FROM ${t}`).run();
  }
  await db
    .prepare(
      `INSERT INTO corpus_versions (version, service, built_at, documents, chunks, loaded_at, is_current)
       VALUES ('v1', 'actas', '2026-11-01', ?1, ?2, 0, 1)`,
    )
    .bind(DOCS, DOCS * 3)
    .run();
  const sections = ["Medical", "Trauma", "Airway", "Cardiac", "Paediatrics", "Obstetrics", "Clinical Skills", "Medicines"];
  const stmts: D1PreparedStatement[] = [];
  for (let d = 0; d < DOCS; d += 1) {
    const id = `DOC_${d}`;
    stmts.push(
      db
        .prepare(
          `INSERT INTO corpus_documents (id, service, kind, number, title, section, scope, checksum, source_type, licence,
             attribution, source_url, corpus_version)
           VALUES (?1, 'actas', 'cmg', ?2, ?3, ?4, 'all', 'sum', 'guideline', 'l', 'a', 'https://cmg.ambulance.act.gov.au', 'v1')`,
        )
        .bind(id, String(d), `Guideline ${d}`, sections[d % sections.length]),
    );
    for (let k = 0; k < 3; k += 1) {
      stmts.push(
        db
          .prepare(
            `INSERT INTO corpus_chunks (id, document_id, ordinal, heading, text, embed_text, vis_ap, vis_ap_pacer, vis_icp,
               vis_icp_pacer, source_type, licence, attribution, corpus_version)
             VALUES (?1, ?2, ?3, 'H', ?4, ?4, ?5, ?5, 1, 1, 'guideline', 'l', 'a', 'v1')`,
          )
          .bind(`ch_${d}_${k}`, id, k, `Chunk ${d}-${k} ${"text ".repeat(120)}`, k === 2 ? 0 : 1),
      );
    }
  }
  for (let q = 0; q < BANK_SIZE; q += 1) {
    const d = q % DOCS;
    const k = q % 3;
    stmts.push(
      db
        .prepare(
          `INSERT INTO question_bank (id, service, document_id, chunk_id, source_text, question_text, question_type, difficulty,
             category, source_citation, gen_view, vis_ap, vis_ap_pacer, vis_icp, vis_icp_pacer, source_type, licence, attribution,
             content_hash, prompt_version, model_id, corpus_version, origin, status, created_at, updated_at)
           SELECT ?1, 'actas', ?2, c.id, c.embed_text, 'Question ' || ?1, 'recall', ?3, 'Medical', 'ACTAS CMG', 'ap',
             c.vis_ap, c.vis_ap_pacer, 1, 1, 'guideline', 'l', 'a', 'hash-' || ?1, 'web-1', 'gemini-3.8-flash', 'v1', 'bank',
             'active', 0, 0
           FROM corpus_chunks c WHERE c.id = ?4`,
        )
        .bind(q.toString(16).padStart(16, "0"), `DOC_${d}`, ["easy", "medium", "hard"][q % 3], `ch_${d}_${k}`),
    );
  }
  for (let i = 0; i < stmts.length; i += 400) await db.batch(stmts.slice(i, i + 400));
}

function mockGemini() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
    Response.json({
      candidates: [
        {
          content: {
            parts: [
              {
                text: JSON.stringify({
                  score: "partial",
                  correct_elements: ["one"],
                  missing_or_wrong: ["two"],
                  source_quote: "text",
                  feedback_summary: "Close.",
                }),
              },
            ],
          },
          finishReason: "STOP",
        },
      ],
      usageMetadata: { promptTokenCount: 1000, candidatesTokenCount: 300 },
    }),
  );
}

describe(`D1 budget: ${USERS} users x ${QUESTIONS_PER_USER} questions on a ${BANK_SIZE}-question bank`, () => {
  beforeAll(async () => {
    await seedBank();
  });

  afterAll(() => vi.restoreAllMocks());

  it("simulates a study session per user and reports rows per request", async ({ annotate }) => {
    const sessions: { cookie: string; view: string }[] = [];
    for (let u = 0; u < USERS; u += 1) {
      const { cookie } = await signIn(`load-${u}-${crypto.randomUUID()}`);
      sessions.push({ cookie, view: u % 3 === 0 ? "icp" : "ap" });
    }
    mockGemini();

    const guestExclude: string[] = [];
    const statuses = new Map<number, number>();
    let firstError = "";
    await Promise.all(
      sessions.map(async ({ cookie, view }, u) => {
        await timed("GET /me", "/api/me", { cookie });
        await timed("GET /progress", `/api/progress?view=${view}&tz=-660`, { cookie });
        for (let i = 0; i < QUESTIONS_PER_USER; i += 1) {
          const res = await post("POST /quiz/next", "/api/quiz/next", { view }, cookie);
          const { question } = (await res.json()) as { question: { id: string } | null };
          if (!question) break;
          if ((i + u) % Math.round(1 / MARK_SHARE) === 0) {
            const marked = await post("POST /quiz/mark", `/api/quiz/questions/${question.id}/mark`, { view, answer: "An answer" }, cookie);
            statuses.set(marked.status, (statuses.get(marked.status) ?? 0) + 1);
            if (marked.status !== 200 && !firstError) firstError = await marked.text();
          } else {
            const revealed = await post("POST /quiz/reveal", `/api/quiz/questions/${question.id}/reveal`, { view }, cookie);
            const { attemptId } = (await revealed.json()) as { attemptId: string };
            await post("POST /quiz/self-grade", `/api/quiz/attempts/${attemptId}/self-grade`, { score: "correct" }, cookie);
          }
        }
        await timed("GET /progress", `/api/progress?view=${view}&tz=-660`, { cookie });
        await timed("GET /progress/history", "/api/progress/history", { cookie });
      }),
    );

    for (let i = 0; i < 20; i += 1) {
      const res = await post("POST /quiz/next (guest)", "/api/quiz/next", { view: "ap", exclude: guestExclude });
      const { question } = (await res.json()) as { question: { id: string } | null };
      if (question) guestExclude.push(question.id);
    }
    await timed("GET /guidelines", "/api/guidelines");
    await timed("GET /guidelines/:id", "/api/guidelines/DOC_1?view=ap");

    const rows = [...tallies.entries()].map(([endpoint, t]) => ({
      endpoint,
      calls: t.calls,
      readsPerCall: Math.round(t.rowsRead / t.calls),
      writesPerCall: Math.round((t.rowsWritten / t.calls) * 10) / 10,
      msPerCall: Math.round(t.ms / t.calls),
    }));
    const perQuestion = (endpoint: string) => rows.find((r) => r.endpoint === endpoint);
    const next = perQuestion("POST /quiz/next")!;
    const mark = perQuestion("POST /quiz/mark")!;
    const reveal = perQuestion("POST /quiz/reveal")!;
    const grade = perQuestion("POST /quiz/self-grade")!;
    const readsPerAnswered =
      next.readsPerCall + MARK_SHARE * mark.readsPerCall + (1 - MARK_SHARE) * (reveal.readsPerCall + grade.readsPerCall);
    const writesPerAnswered =
      next.writesPerCall + MARK_SHARE * mark.writesPerCall + (1 - MARK_SHARE) * (reveal.writesPerCall + grade.writesPerCall);
    const summary = {
      users: USERS,
      questionsPerUser: QUESTIONS_PER_USER,
      bank: BANK_SIZE,
      readsPerAnsweredQuestion: Math.round(readsPerAnswered),
      writesPerAnsweredQuestion: Math.round(writesPerAnswered * 10) / 10,
      answeredQuestionsPerDayOnFreeReads: Math.floor(FREE_TIER.rowsReadPerDay / readsPerAnswered),
      answeredQuestionsPerDayOnFreeWrites: Math.floor(FREE_TIER.rowsWrittenPerDay / writesPerAnswered),
    };
    await annotate(`D1_BUDGET ${JSON.stringify({ rows, summary, markStatuses: Object.fromEntries(statuses), firstError }, null, 2)}`);
    expect(next.calls).toBeGreaterThan(0);
  }, 600_000);
});
