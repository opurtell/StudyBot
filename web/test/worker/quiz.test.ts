import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { questionHash, retireStaleQuestions } from "../../src/worker/quiz/bank";
import { UNREADABLE_MARK_MESSAGE } from "../../src/worker/quiz/routes";
import { takeCredit } from "../../src/worker/quiz/usage";
import { addQuestion, ALL, CHUNK_TEXT, ICP_ONLY, Q_AP, Q_AP2, Q_ICP, seed } from "./fixtures";
import { call, freshIp, postJson, signIn } from "./helpers";

afterEach(() => vi.restoreAllMocks());

beforeEach(async () => {
  await seed();
  await addQuestion(Q_AP, "ch_ap", ALL);
  await addQuestion(Q_AP2, "ch_ap2", ALL, { difficulty: "hard" });
  await addQuestion(Q_ICP, "ch_icp", ICP_ONLY);
});

function geminiReply(text: string, status = 200) {
  const spy = vi.spyOn(globalThis, "fetch");
  spy.mockClear();
  return spy.mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (!url.startsWith("https://gateway.ai.cloudflare.com/")) throw new Error(`Unexpected fetch ${url}`);
    if (status !== 200) return new Response("upstream broke", { status });
    return Response.json({
      candidates: [{ content: { parts: [{ text }] }, finishReason: "STOP" }],
      usageMetadata: { promptTokenCount: 1000, candidatesTokenCount: 100 },
    });
  });
}

async function next(body: Record<string, unknown>, cookie?: string) {
  const res = await postJson("/api/quiz/next", body, { cookie });
  return { res, body: (await res.json()) as { question: { id: string; origin: string } | null; exhausted: boolean; canGenerate: boolean; quota: unknown } };
}

async function userRow(email: string) {
  return env.DB.prepare(`SELECT id, free_gen_used, free_eval_used FROM users WHERE email = ?1`)
    .bind(email)
    .first<{ id: string; free_gen_used: number; free_eval_used: number }>();
}

describe("serving from the bank", () => {
  it("never gives an AP user an ICP-only question", async () => {
    const seen = new Set<string>();
    const exclude: string[] = [];
    for (let i = 0; i < 3; i += 1) {
      const { body } = await next({ view: "ap", exclude });
      if (body.question) {
        seen.add(body.question.id);
        exclude.push(body.question.id);
      }
    }
    expect([...seen].sort()).toEqual([Q_AP, Q_AP2]);
    const { body } = await next({ view: "ap", exclude });
    expect(body).toMatchObject({ question: null, exhausted: true, canGenerate: false, quota: null });
  });

  it("serves ICP questions to ICP users and filters by guideline and difficulty", async () => {
    expect((await next({ view: "icp", documentId: "CMG_3A_RSI" })).body.question?.id).toBe(Q_ICP);
    expect((await next({ view: "icp_pacer", difficulty: "hard" })).body.question?.id).toBe(Q_AP2);
    expect((await next({ view: "ap", section: "Airway" })).body.question).toBeNull();
  });

  it("remembers what a signed-in user has seen and repeats only when asked", async () => {
    const { cookie } = await signIn();
    const first = await next({ view: "ap" }, cookie);
    const second = await next({ view: "ap" }, cookie);
    expect(new Set([first.body.question?.id, second.body.question?.id])).toEqual(new Set([Q_AP, Q_AP2]));
    const third = await next({ view: "ap" }, cookie);
    expect(third.body).toMatchObject({ question: null, exhausted: true, canGenerate: true });
    const again = await next({ view: "ap", repeat: true }, cookie);
    expect(again.body.question?.id).toBe(first.body.question?.id);
  });

  it("stops serving a question once its source text changes, and the cron retires it", async () => {
    await env.DB.prepare(`UPDATE corpus_chunks SET embed_text = 'changed' WHERE id = 'ch_ap'`).run();
    const exclude = [Q_AP2];
    expect((await next({ view: "ap", exclude })).body.question).toBeNull();
    expect(await retireStaleQuestions(env.DB, Date.now())).toBe(1);
    const row = await env.DB.prepare(`SELECT status, status_reason FROM question_bank WHERE id = ?1`).bind(Q_AP).first();
    expect(row).toEqual({ status: "retired", status_reason: "source_changed" });
  });

  it("does not serve withdrawn questions", async () => {
    await env.DB.prepare(`UPDATE question_bank SET status = 'flagged' WHERE id = ?1`).bind(Q_AP).run();
    expect((await next({ view: "ap", exclude: [Q_AP2] })).body.question).toBeNull();
  });

  it("rejects bad input", async () => {
    expect((await postJson("/api/quiz/next", { view: "paramedic" })).status).toBe(400);
    expect((await postJson("/api/quiz/next", { difficulty: "brutal" })).status).toBe(400);
    expect((await postJson("/api/quiz/next", { exclude: ["not-an-id"] })).status).toBe(400);
  });
});

describe("reveal", () => {
  it("returns the source text without calling the model, and respects scope", async () => {
    const spy = vi.spyOn(globalThis, "fetch");
    const res = await postJson(`/api/quiz/questions/${Q_AP}/reveal`, { view: "ap" });
    expect(res.status).toBe(200);
    const body = (await res.json()) as { score: null; sourceText: string; citation: string };
    expect(body.score).toBeNull();
    expect(body.sourceText).toBe(`[ACTAS] ch_ap ${CHUNK_TEXT}`);
    expect(spy).not.toHaveBeenCalled();
    expect((await postJson(`/api/quiz/questions/${Q_ICP}/reveal`, { view: "ap" })).status).toBe(404);
  });
});

const GOOD_MARK = JSON.stringify({
  score: "partial",
  correct_elements: ["oral glucose"],
  missing_or_wrong: "not a list",
  source_quote: "x",
  feedback_summary: "Mostly there.",
});

describe("AI marking", () => {
  it("needs sign-in", async () => {
    const res = await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Give glucose" });
    expect(res.status).toBe(401);
  });

  it("marks against the stored chunk only, records the attempt and takes one credit", async () => {
    const { cookie, email } = await signIn();
    const spy = geminiReply(GOOD_MARK);
    const res = await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Give oral glucose", elapsedMs: 4000 }, { cookie });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown> & { quota: { marking: { used: number } } };
    expect(body).toMatchObject({ score: "partial", correctElements: ["oral glucose"], missingOrWrong: [], feedbackSummary: "Mostly there." });
    expect(body.quota.marking.used).toBe(1);

    const sent = JSON.parse(String(spy.mock.calls[0]?.[1]?.body)) as { contents: { parts: { text: string }[] }[] };
    expect(sent.contents[0]?.parts[0]?.text).toBe(
      `Question: Question ${Q_AP}\n\nSource material:\n[ACTAS] ch_ap ${CHUNK_TEXT}\n\nStudent answer: Give oral glucose`,
    );

    const user = await userRow(email);
    expect(user?.free_eval_used).toBe(1);
    const attempt = await env.DB.prepare(`SELECT kind, score, elapsed_ms FROM attempts WHERE user_id = ?1`).bind(user?.id).first();
    expect(attempt).toEqual({ kind: "marked", score: "partial", elapsed_ms: 4000 });
    const ledger = await env.DB.prepare(`SELECT kind, outcome, tokens_in, cost_usd_micros FROM usage_ledger`).first();
    expect(ledger).toEqual({ kind: "eval", outcome: "ok", tokens_in: 1000, cost_usd_micros: 550 });
  });

  it("does not score or charge for an unreadable reply", async () => {
    const { cookie, email } = await signIn();
    for (const reply of ["Looks good to me!", JSON.stringify({ score: "great" }), JSON.stringify([{ score: "correct" }])]) {
      geminiReply(reply);
      const res = await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Give glucose" }, { cookie });
      expect(res.status).toBe(502);
      expect(await res.json()).toMatchObject({ error: "unreadable_response", message: UNREADABLE_MARK_MESSAGE });
    }
    expect((await userRow(email))?.free_eval_used).toBe(0);
    expect(await env.DB.prepare(`SELECT COUNT(*) AS n FROM attempts`).first()).toEqual({ n: 0 });
    const ledger = await env.DB.prepare(`SELECT outcome, COUNT(*) AS n FROM usage_ledger GROUP BY outcome`).all();
    expect(ledger.results).toEqual([{ outcome: "unreadable", n: 3 }]);
  });

  it("refunds when the model call fails", async () => {
    const { cookie, email } = await signIn();
    geminiReply("", 500);
    const res = await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Give glucose" }, { cookie });
    expect(res.status).toBe(502);
    expect((await userRow(email))?.free_eval_used).toBe(0);
  });

  it("stops at the monthly allowance", async () => {
    const { cookie, email } = await signIn();
    const period = new Date().toISOString().slice(0, 7);
    await env.DB.prepare(`UPDATE users SET free_eval_used = 30, quota_period = ?2 WHERE email = ?1`).bind(email, period).run();
    const spy = vi.spyOn(globalThis, "fetch");
    spy.mockClear();
    const res = await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Give glucose" }, { cookie });
    expect(res.status).toBe(429);
    expect(await res.json()).toMatchObject({ error: "quota_exhausted" });
    expect(spy).not.toHaveBeenCalled();
  });

  it("resets the allowance in a new month", async () => {
    const { email } = await signIn();
    await env.DB.prepare(`UPDATE users SET free_eval_used = 30, free_gen_used = 20, quota_period = '2020-01' WHERE email = ?1`).bind(email).run();
    const user = await userRow(email);
    expect(await takeCredit(env.DB, env, user!.id, "eval", new Date())).toBe(true);
    expect(await userRow(email)).toMatchObject({ free_eval_used: 1, free_gen_used: 0 });
  });

  it("never lets concurrent requests overshoot the allowance", async () => {
    const { email } = await signIn();
    const period = new Date().toISOString().slice(0, 7);
    await env.DB.prepare(`UPDATE users SET free_eval_used = 28, quota_period = ?2 WHERE email = ?1`).bind(email, period).run();
    const user = await userRow(email);
    const results = await Promise.all(Array.from({ length: 6 }, () => takeCredit(env.DB, env, user!.id, "eval", new Date())));
    expect(results.filter(Boolean)).toHaveLength(2);
    expect((await userRow(email))?.free_eval_used).toBe(30);
  });

  it("honours the admin kill switch", async () => {
    await env.DB.prepare(`INSERT INTO app_flags (key, value, updated_at) VALUES ('live_ai', 'off', 0)`).run();
    const { cookie } = await signIn();
    const res = await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Give glucose" }, { cookie });
    expect(res.status).toBe(503);
  });

  it("refuses withdrawn questions and empty answers", async () => {
    const { cookie } = await signIn();
    expect((await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "  " }, { cookie })).status).toBe(400);
    await env.DB.prepare(`UPDATE question_bank SET status = 'flagged' WHERE id = ?1`).bind(Q_AP).run();
    expect((await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "x" }, { cookie })).status).toBe(404);
  });
});

describe("live generation", () => {
  const reply = (text: string, index: number | string) =>
    JSON.stringify({ question_text: text, question_type: "recall", source_citation: "ACTAS CMG 10", category: "Medical", source_index: index });

  it("banks the question against the chunk the model chose and charges one credit", async () => {
    const { cookie, email } = await signIn();
    const spy = geminiReply(reply("What BGL defines hypoglycaemia in CMG 10?", "2"));
    const res = await postJson("/api/quiz/generate", { view: "ap", documentId: "CMG_10_Diabetic" }, { cookie });
    expect(res.status).toBe(200);
    const body = (await res.json()) as { question: { id: string; origin: string }; duplicate: boolean };
    expect(body).toMatchObject({ duplicate: false, question: { origin: "live" } });

    const sent = JSON.parse(String(spy.mock.calls[0]?.[1]?.body)) as { contents: { parts: { text: string }[] }[] };
    const userText = sent.contents[0]?.parts[0]?.text ?? "";
    const order = [...userText.matchAll(/\[ACTAS\] (ch_\w+)/g)].map((m) => m[1]);
    expect(order).toHaveLength(2);
    expect(userText).not.toContain("ch_icp");

    const row = await env.DB.prepare(`SELECT chunk_id, vis_ap, vis_icp, origin, gen_view FROM question_bank WHERE id = ?1`)
      .bind(body.question.id)
      .first();
    expect(row).toEqual({ chunk_id: order[1], vis_ap: 1, vis_icp: 1, origin: "live", gen_view: "ap" });
    expect((await userRow(email))?.free_gen_used).toBe(1);
    // The model named the guideline by number only, so the title is added before banking.
    const named = "What BGL defines hypoglycaemia in the Diabetic Emergencies guideline (CMG 10)?";
    expect(body.question.id).toBe((await questionHash(named)).slice(0, 16));
    const stored = await env.DB.prepare(`SELECT question_text FROM question_bank WHERE id = ?1`).bind(body.question.id).first();
    expect(stored).toEqual({ question_text: named });
  });

  it("keeps a question that names ICP-only care away from AP users", async () => {
    const { cookie } = await signIn();
    geminiReply(reply("When is amiodarone given for VF?", 1));
    const res = await postJson("/api/quiz/generate", { view: "ap" }, { cookie });
    expect(res.status).toBe(502);
    const row = await env.DB.prepare(`SELECT vis_ap, vis_ap_pacer, vis_icp FROM question_bank WHERE origin = 'live'`).first();
    expect(row).toEqual({ vis_ap: 0, vis_ap_pacer: 0, vis_icp: 1 });
  });

  it("refunds an unreadable reply and a duplicate", async () => {
    const { cookie, email } = await signIn();
    geminiReply("no json here");
    expect((await postJson("/api/quiz/generate", { view: "ap" }, { cookie })).status).toBe(502);
    expect((await userRow(email))?.free_gen_used).toBe(0);

    await env.DB.prepare(`UPDATE question_bank SET content_hash = ?1 WHERE id = ?2`)
      .bind(await questionHash("Question dup?  "), Q_AP)
      .run();
    geminiReply(reply("question DUP?", 1));
    const res = await postJson("/api/quiz/generate", { view: "ap" }, { cookie });
    expect(await res.json()).toMatchObject({ duplicate: true, question: { id: Q_AP } });
    expect((await userRow(email))?.free_gen_used).toBe(0);
  });

  it("needs sign-in", async () => {
    expect((await postJson("/api/quiz/generate", { view: "ap" })).status).toBe(401);
  });
});

describe("reporting a question", () => {
  it("withdraws a question after two different people report it", async () => {
    const first = await postJson(`/api/quiz/questions/${Q_AP}/report`, { reason: "incorrect", detail: "Wrong dose" }, { ip: "198.51.100.1" });
    expect(await first.json()).toEqual({ ok: true, withdrawn: false });
    const repeat = await postJson(`/api/quiz/questions/${Q_AP}/report`, { reason: "unclear" }, { ip: "198.51.100.1" });
    expect(await repeat.json()).toEqual({ ok: true, withdrawn: false });
    const { cookie } = await signIn();
    const second = await postJson(`/api/quiz/questions/${Q_AP}/report`, { reason: "not_in_source" }, { cookie });
    expect(await second.json()).toEqual({ ok: true, withdrawn: true });
    expect((await next({ view: "ap", exclude: [Q_AP2] })).body.question).toBeNull();
  });

  it("withdraws immediately when an admin reports, and the admin can restore or retire", async () => {
    const { cookie, email } = await signIn();
    await env.DB.prepare(`UPDATE users SET is_admin = 1 WHERE email = ?1`).bind(email).run();
    const res = await postJson(`/api/quiz/questions/${Q_AP}/report`, { reason: "out_of_scope" }, { cookie });
    expect(await res.json()).toEqual({ ok: true, withdrawn: true });

    const admin = (await (await call("/api/admin/questions", { cookie })).json()) as {
      reported: { id: string; reports: { reason: string }[] }[];
      summary: { byStatus: Record<string, number> };
    };
    expect(admin.reported.map((r) => r.id)).toEqual([Q_AP]);
    expect(admin.reported[0]?.reports[0]?.reason).toBe("out_of_scope");
    expect(admin.summary.byStatus).toMatchObject({ active: 2, flagged: 1 });

    expect((await postJson(`/api/admin/questions/${Q_AP}/status`, { status: "active" }, { cookie })).status).toBe(200);
    const after = (await (await call("/api/admin/questions", { cookie })).json()) as { reported: unknown[] };
    expect(after.reported).toEqual([]);
  });

  it("validates the reason and the question", async () => {
    expect((await postJson(`/api/quiz/questions/${Q_AP}/report`, { reason: "boring" })).status).toBe(400);
    expect((await postJson(`/api/quiz/questions/cccccccccccccccc/report`, { reason: "other" })).status).toBe(404);
  });
});

describe("admin question API", () => {
  it("is admin only", async () => {
    expect((await call("/api/admin/questions", { ip: freshIp() })).status).toBe(401);
    const { cookie } = await signIn();
    expect((await call("/api/admin/questions", { cookie })).status).toBe(403);
    expect((await postJson("/api/admin/questions/live-ai", { enabled: false }, { cookie })).status).toBe(403);
  });

  it("turns live AI off and on", async () => {
    const { cookie, email } = await signIn();
    await env.DB.prepare(`UPDATE users SET is_admin = 1 WHERE email = ?1`).bind(email).run();
    expect(await (await postJson("/api/admin/questions/live-ai", { enabled: false }, { cookie })).json()).toEqual({ liveAi: false });
    const { body } = await next({ view: "ap", exclude: [Q_AP, Q_AP2] }, cookie);
    expect(body.canGenerate).toBe(false);
    await postJson("/api/admin/questions/live-ai", { enabled: true }, { cookie });
    expect((await next({ view: "ap", exclude: [Q_AP, Q_AP2] }, cookie)).body.canGenerate).toBe(true);
  });
});
