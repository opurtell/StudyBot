import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextQuestion } from "../../src/worker/quiz/bank";
import { startOfUtcDay } from "../../src/worker/quiz/usage";
import { addQuestion, ALL, ICP_ONLY, Q_AP, Q_AP2, Q_ICP, seed } from "./fixtures";
import { call, postJson, signIn } from "./helpers";

const MARK = JSON.stringify({
  score: "correct",
  correct_elements: ["glucose"],
  missing_or_wrong: [],
  source_quote: "x",
  feedback_summary: "Good.",
});

function gemini(text = MARK) {
  const spy = vi.spyOn(globalThis, "fetch");
  spy.mockClear();
  spy.mockImplementation(async () =>
    Response.json({
      candidates: [{ content: { parts: [{ text }] }, finishReason: "STOP" }],
      usageMetadata: { promptTokenCount: 1000, candidatesTokenCount: 100 },
    }),
  );
  return spy;
}

async function used(email: string) {
  return env.DB.prepare(`SELECT free_eval_used, free_gen_used FROM users WHERE email = ?1`)
    .bind(email)
    .first<{ free_eval_used: number; free_gen_used: number }>();
}

afterEach(() => vi.restoreAllMocks());

beforeEach(async () => {
  await seed();
  await addQuestion(Q_AP, "ch_ap", ALL);
  await addQuestion(Q_AP2, "ch_ap2", ALL, { difficulty: "hard" });
  await addQuestion(Q_ICP, "ch_icp", ICP_ONLY);
});

describe("quota abuse", () => {
  it("lets a burst of parallel marking requests through only up to the allowance, and calls the model once per credit", async () => {
    const { cookie, email } = await signIn();
    const period = new Date().toISOString().slice(0, 7);
    await env.DB.prepare(`UPDATE users SET free_eval_used = 25, quota_period = ?2 WHERE email = ?1`).bind(email, period).run();
    const spy = gemini();
    const results = await Promise.all(
      Array.from({ length: 12 }, () => postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Give glucose" }, { cookie })),
    );
    const statuses = results.map((r) => r.status).sort();
    expect(statuses.filter((s) => s === 200)).toHaveLength(5);
    expect(statuses.filter((s) => s === 429)).toHaveLength(7);
    expect(spy).toHaveBeenCalledTimes(5);
    expect((await used(email))?.free_eval_used).toBe(30);
  });

  it("charges every time the same question is marked again", async () => {
    const { cookie, email } = await signIn();
    gemini();
    for (let i = 0; i < 3; i += 1) {
      expect((await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Give glucose" }, { cookie })).status).toBe(200);
    }
    expect((await used(email))?.free_eval_used).toBe(3);
  });

  it("ignores client-supplied quota fields and has no client refund route", async () => {
    const { cookie, email } = await signIn();
    gemini();
    await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Glucose", refund: true, quota: 0, free_eval_used: 0 }, { cookie });
    expect((await used(email))?.free_eval_used).toBe(1);
    for (const path of ["/api/quiz/refund", "/api/me/quota", "/api/quiz/questions/aaaaaaaaaaaaaaa1/refund"]) {
      expect((await postJson(path, {}, { cookie })).status).toBe(404);
    }
    expect((await call("/api/me/settings", { method: "PUT", headers: { "content-type": "application/json", origin: "https://studybot.test" }, body: JSON.stringify({ quota: 0 }), cookie })).status).toBe(400);
  });

  it("refuses oversized answers before spending anything", async () => {
    const { cookie, email } = await signIn();
    const spy = gemini();
    const res = await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "a".repeat(4001) }, { cookie });
    expect(res.status).toBe(400);
    expect(spy).not.toHaveBeenCalled();
    expect((await used(email))?.free_eval_used).toBe(0);
  });

  it("stops all accounts once the site-wide daily marking cap is reached", async () => {
    await env.DB.prepare(`INSERT INTO daily_usage (day, kind, calls) VALUES (?1, 'eval', 1000)`).bind(startOfUtcDay(Date.now())).run();
    const { cookie, email } = await signIn();
    const spy = gemini();
    const res = await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Glucose" }, { cookie });
    expect(res.status).toBe(503);
    expect(spy).not.toHaveBeenCalled();
    expect((await used(email))?.free_eval_used).toBe(0);
  });

  it("counts every model call, including failures, toward the daily cap", async () => {
    const { cookie } = await signIn();
    gemini("not json");
    await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Glucose" }, { cookie });
    gemini();
    await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "Glucose" }, { cookie });
    const row = await env.DB.prepare(`SELECT calls FROM daily_usage WHERE kind = 'eval'`).first<{ calls: number }>();
    expect(row?.calls).toBe(2);
  });

  it("rejects cross-site and non-JSON writes", async () => {
    const { cookie } = await signIn();
    expect((await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "x" }, { cookie, origin: "https://evil.example" })).status).toBe(403);
    expect((await postJson(`/api/quiz/questions/${Q_AP}/mark`, { view: "ap", answer: "x" }, { cookie, origin: null })).status).toBe(403);
    const form = await call(`/api/quiz/questions/${Q_AP}/mark`, {
      method: "POST",
      headers: { origin: "https://studybot.test", "content-type": "text/plain" },
      body: "answer=x",
      cookie,
    });
    expect(form.status).toBe(415);
  });
});

describe("report abuse", () => {
  it("never withdraws a question on anonymous reports alone, however many addresses send them", async () => {
    for (let i = 1; i <= 5; i += 1) {
      const res = await postJson(`/api/quiz/questions/${Q_AP}/report`, { reason: "incorrect" }, { ip: `192.0.2.${i}` });
      expect(await res.json()).toEqual({ ok: true, withdrawn: false });
    }
    const row = await env.DB.prepare(`SELECT status, times_reported FROM question_bank WHERE id = ?1`).bind(Q_AP).first();
    expect(row).toEqual({ status: "active", times_reported: 5 });
  });

  it("caps how many reports one account or address can send in a day", async () => {
    const { cookie } = await signIn();
    const ids = Array.from({ length: 21 }, (_, i) => `ccccccccccccc${i.toString().padStart(3, "0")}`);
    for (const id of ids) await addQuestion(id, "ch_ap", ALL);
    const statuses: number[] = [];
    for (const id of ids) statuses.push((await postJson(`/api/quiz/questions/${id}/report`, { reason: "unclear" }, { cookie })).status);
    expect(statuses.slice(0, 20).every((s) => s === 200)).toBe(true);
    expect(statuses[20]).toBe(429);
  });

  it("drops a deleted account's link to its reports", async () => {
    const { cookie } = await signIn();
    await postJson(`/api/quiz/questions/${Q_AP}/report`, { reason: "other", detail: "My name is in here" }, { cookie });
    const res = await call("/api/me", { method: "DELETE", headers: { origin: "https://studybot.test" }, cookie });
    expect(res.status).toBe(200);
    const row = await env.DB.prepare(`SELECT user_id, reporter_key, detail FROM question_reports`).first<{ user_id: string | null; reporter_key: string; detail: string | null }>();
    expect(row?.user_id).toBeNull();
    expect(row?.detail).toBeNull();
    expect(row?.reporter_key.startsWith("deleted:")).toBe(true);
  });
});

describe("serving", () => {
  it("always finds the only matching question, whatever the random starting point", async () => {
    const original = Math.random;
    try {
      for (const start of [0, 0.000001, 0.25, 0.5, 0.75, 0.999999]) {
        Math.random = () => start;
        const q = await nextQuestion(env.DB, {
          view: "icp_pacer",
          filters: { documentId: null, section: null, difficulty: "hard" },
          userId: null,
          exclude: [],
          repeat: false,
        });
        expect(q?.id).toBe(Q_AP2);
      }
    } finally {
      Math.random = original;
    }
  });

  it("gives a guest every question in scope before running out", async () => {
    const seen = new Set<string>();
    for (let i = 0; i < 4; i += 1) {
      const q = await nextQuestion(env.DB, {
        view: "icp",
        filters: { documentId: null, section: null, difficulty: null },
        userId: null,
        exclude: [...seen],
        repeat: false,
      });
      if (q) seen.add(q.id);
    }
    expect([...seen].sort()).toEqual([Q_AP, Q_AP2, Q_ICP]);
  });
});
