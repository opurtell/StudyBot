import { env } from "cloudflare:workers";
import { beforeEach, describe, expect, it } from "vitest";
import { summariseProgress, type ProgressRow } from "../../src/shared/progress";
import { addQuestion, ALL, ICP_ONLY, Q_AP, Q_AP2, Q_ICP, seed } from "./fixtures";
import { call, ORIGIN, postJson, signIn } from "./helpers";

beforeEach(async () => {
  await seed();
  await addQuestion(Q_AP, "ch_ap", ALL);
  await addQuestion(Q_AP2, "ch_ap2", ALL, { difficulty: "hard" });
  await addQuestion(Q_ICP, "ch_icp", ICP_ONLY);
});

function send(method: string, path: string, body: unknown, cookie?: string) {
  return call(path, {
    method,
    headers: { "content-type": "application/json", origin: ORIGIN },
    body: JSON.stringify(body),
    cookie,
  });
}

async function json<T = Record<string, unknown>>(res: Response): Promise<T> {
  return (await res.json()) as T;
}

describe("per-user settings", () => {
  it("starts unsaved, saves qualification and exclusions, and validates them", async () => {
    const { cookie } = await signIn();
    const before = await json<{ settings: unknown }>(await call("/api/me", { cookie }));
    expect(before.settings).toEqual({ qualification: null, pacer: false, excludedSections: [], excludedDocuments: [], saved: false });

    const saved = { qualification: "ap", pacer: true, excludedSections: ["Airway"], excludedDocuments: ["CMG_10_Diabetic"] };
    expect((await send("PUT", "/api/me/settings", saved, cookie)).status).toBe(200);
    const after = await json<{ settings: unknown }>(await call("/api/me", { cookie }));
    expect(after.settings).toEqual({ ...saved, saved: true });

    expect((await send("PUT", "/api/me/settings", { ...saved, qualification: "emt" }, cookie)).status).toBe(400);
    expect((await send("PUT", "/api/me/settings", { ...saved, excludedSections: [1] }, cookie)).status).toBe(400);
    expect((await send("PUT", "/api/me/settings", saved)).status).toBe(401);
  });

  it("keeps each user's settings separate and removes them with the account", async () => {
    const a = await signIn();
    const b = await signIn();
    await send("PUT", "/api/me/settings", { qualification: "icp", pacer: false, excludedSections: [], excludedDocuments: [] }, a.cookie);
    const aId = (await env.DB.prepare(`SELECT id FROM users WHERE email = ?1`).bind(a.email).first<{ id: string }>())!.id;
    await postJson("/api/progress/import", { attempts: [{ questionId: Q_AP, score: "correct", at: Date.now() }] }, { cookie: a.cookie });
    const bMe = await json<{ settings: { saved: boolean } }>(await call("/api/me", { cookie: b.cookie }));
    expect(bMe.settings.saved).toBe(false);
    await call("/api/me", { method: "DELETE", headers: { origin: ORIGIN }, cookie: a.cookie });
    for (const table of ["user_settings", "attempts", "user_question_seen"]) {
      const left = await env.DB.prepare(`SELECT COUNT(*) AS n FROM ${table} WHERE user_id = ?1`).bind(aId).first<{ n: number }>();
      expect(left?.n).toBe(0);
    }
  });
});

describe("excluded topics", () => {
  it("skips excluded sections and guidelines unless the user picks one", async () => {
    const next = async (body: Record<string, unknown>) =>
      (await json<{ question: { id: string; section: string } | null }>(await postJson("/api/quiz/next", body))).question;
    const q = await next({ view: "icp", excludedSections: ["Medical"] });
    expect(q?.id).toBe(Q_ICP);
    expect(q?.section).toBe("Airway");
    expect((await next({ view: "icp", excludedDocuments: ["CMG_3A_RSI"], exclude: [Q_AP, Q_AP2] }))).toBeNull();
    expect((await next({ view: "icp", excludedDocuments: ["CMG_3A_RSI"], documentId: "CMG_3A_RSI" }))?.id).toBe(Q_ICP);
    expect((await postJson("/api/quiz/next", { view: "icp", excludedSections: "Medical" })).status).toBe(400);
  });
});

describe("topics", () => {
  it("counts active questions per section in the chosen view", async () => {
    const ap = await json<{ topics: { section: string; questions: number }[] }>(await call("/api/topics?view=ap"));
    expect(ap.topics).toEqual([expect.objectContaining({ section: "Medical", questions: 2 })]);
    const icp = await json<{ topics: { section: string; questions: number }[] }>(await call("/api/topics?view=icp"));
    expect(icp.topics.map((t) => [t.section, t.questions])).toEqual([
      ["Airway", 1],
      ["Medical", 2],
    ]);
  });
});

describe("progress", () => {
  it("needs sign-in", async () => {
    expect((await call("/api/progress?view=ap")).status).toBe(401);
    expect((await postJson("/api/progress/import", { attempts: [] })).status).toBe(401);
  });

  it("records a self-marked reveal and summarises mastery by guideline section", async () => {
    const { cookie } = await signIn();
    const reveal = await json<{ attemptId: string; section: string }>(
      await postJson(`/api/quiz/questions/${Q_AP}/reveal`, { view: "ap", answer: "Below 4" }, { cookie }),
    );
    expect(reveal.section).toBe("Medical");
    expect((await postJson(`/api/quiz/attempts/${reveal.attemptId}/self-grade`, { score: "partial" }, { cookie })).status).toBe(200);
    const r2 = await json<{ attemptId: string }>(await postJson(`/api/quiz/questions/${Q_ICP}/reveal`, { view: "icp" }, { cookie }));
    await postJson(`/api/quiz/attempts/${r2.attemptId}/self-grade`, { score: "correct" }, { cookie });

    const progress = await json<{
      sections: { section: string; answered: number; percent: number | null; status: string }[];
      totals: { answered: number; accuracy: number; streakDays: number };
      recent: { id: string; score: string }[];
      weakest: { section: string; documentTitle: string };
    }>(await call("/api/progress?view=icp&tz=-600", { cookie }));
    expect(progress.sections).toEqual([
      expect.objectContaining({ section: "Airway", answered: 1, percent: 100, status: "strong" }),
      expect.objectContaining({ section: "Medical", answered: 1, percent: 50, status: "developing" }),
    ]);
    expect(progress.totals).toMatchObject({ answered: 2, accuracy: 50, streakDays: 1 });
    expect(progress.weakest).toMatchObject({ section: "Medical", documentTitle: "Diabetic Emergencies" });
    expect(progress.recent).toHaveLength(2);

    const detail = await json<{ answer: string; score: string; sourceText: string; documentTitle: string }>(
      await call(`/api/progress/attempts/${reveal.attemptId}`, { cookie }),
    );
    expect(detail).toMatchObject({ answer: "Below 4", score: "partial", documentTitle: "Diabetic Emergencies" });

    const other = await signIn();
    expect((await call(`/api/progress/attempts/${reveal.attemptId}`, { cookie: other.cookie })).status).toBe(404);
    expect((await postJson(`/api/quiz/attempts/${reveal.attemptId}/self-grade`, { score: "correct" }, { cookie: other.cookie })).status).toBe(404);
    expect((await postJson(`/api/quiz/attempts/${reveal.attemptId}/self-grade`, { score: "great" }, { cookie })).status).toBe(400);
  });

  it("pages through history newest first", async () => {
    const { cookie } = await signIn();
    const userId = (await json<{ email: string }>(await call("/api/me", { cookie }))).email;
    const id = (await env.DB.prepare(`SELECT id FROM users WHERE email = ?1`).bind(userId).first<{ id: string }>())!.id;
    const stmts = Array.from({ length: 25 }, (_, i) =>
      env.DB.prepare(`INSERT INTO attempts (id, user_id, question_id, kind, score, created_at) VALUES (?1, ?2, ?3, 'revealed', 'correct', ?4)`).bind(
        `h${i}`,
        id,
        Q_AP,
        1_000 + i,
      ),
    );
    await env.DB.batch(stmts);
    const first = await json<{ items: { id: string; at: number }[]; more: boolean }>(await call("/api/progress/history", { cookie }));
    expect(first.items).toHaveLength(20);
    expect(first.items[0]?.id).toBe("h24");
    expect(first.more).toBe(true);
    const second = await json<{ items: { id: string }[]; more: boolean }>(
      await call(`/api/progress/history?before=${first.items.at(-1)!.at}`, { cookie }),
    );
    expect(second.items.map((i) => i.id)).toEqual(["h4", "h3", "h2", "h1", "h0"]);
    expect(second.more).toBe(false);
  });

  it("imports guest progress once, skipping unknown questions and bad timestamps", async () => {
    const { cookie } = await signIn();
    const now = Date.now();
    const attempts = [
      { questionId: Q_AP, score: "correct", at: now - 86_400_000 },
      { questionId: Q_AP2, score: null, at: now - 1000 },
      { questionId: "ffffffffffffffff", score: "correct", at: now },
      { questionId: Q_ICP, score: "correct", at: now + 86_400_000 },
      { questionId: Q_ICP, score: "brilliant", at: now },
    ];
    const first = await json(await postJson("/api/progress/import", { attempts }, { cookie }));
    expect(first).toEqual({ imported: 2, skipped: 3 });
    const again = await json(await postJson("/api/progress/import", { attempts }, { cookie }));
    expect(again).toEqual({ imported: 0, skipped: 5 });

    const progress = await json<{ totals: { answered: number; streakDays: number } }>(await call("/api/progress?view=ap", { cookie }));
    expect(progress.totals).toMatchObject({ answered: 1, streakDays: 2 });
    const next = await json<{ question: unknown }>(await postJson("/api/quiz/next", { view: "ap" }, { cookie }));
    expect(next.question).toBeNull();

    const tooMany = Array.from({ length: 201 }, () => attempts[0]);
    expect((await postJson("/api/progress/import", { attempts: tooMany }, { cookie })).status).toBe(400);
  });

  it("resets a user's progress", async () => {
    const { cookie } = await signIn();
    await postJson("/api/progress/import", { attempts: [{ questionId: Q_AP, score: "correct", at: Date.now() }] }, { cookie });
    expect((await call("/api/progress", { method: "DELETE", headers: { origin: ORIGIN }, cookie })).status).toBe(200);
    const progress = await json<{ totals: { answered: number } }>(await call("/api/progress?view=ap", { cookie }));
    expect(progress.totals.answered).toBe(0);
    expect((await json<{ question: unknown }>(await postJson("/api/quiz/next", { view: "ap" }, { cookie }))).question).not.toBeNull();
  });
});

describe("summariseProgress", () => {
  const row = (questionId: string, score: ProgressRow["score"], at: number, section = "Medical"): ProgressRow => ({
    questionId,
    documentId: `doc-${section}`,
    documentTitle: `${section} guideline`,
    section,
    score,
    at,
  });
  const DAY = 86_400_000;
  const now = Date.UTC(2026, 10, 2, 1, 0);

  it("uses each question's latest score so re-marking can't inflate mastery", () => {
    const s = summariseProgress([row("a", "incorrect", now - 3000), row("a", "incorrect", now - 2000), row("a", "correct", now - 1000)], [], {
      now,
      tzOffsetMinutes: 0,
    });
    expect(s.sections[0]).toMatchObject({ answered: 1, percent: 100, status: "strong" });
  });

  it("lists untouched sections as new and counts study-day streaks in local time", () => {
    const s = summariseProgress(
      [row("a", "correct", now - DAY), row("b", null, now - 2 * DAY), row("c", "incorrect", now - 4 * DAY)],
      [{ section: "Trauma", questions: 9, documents: [] }],
      { now, tzOffsetMinutes: 0 },
    );
    expect(s.sections.map((x) => [x.section, x.status])).toEqual([
      ["Medical", "developing"],
      ["Trauma", "new"],
    ]);
    expect(s.totals).toEqual({ answered: 2, accuracy: 50, streakDays: 2, studiedToday: false });
    const sydney = summariseProgress([row("a", "correct", Date.UTC(2026, 10, 1, 14, 0))], [], { now, tzOffsetMinutes: -660 });
    expect(sydney.totals).toMatchObject({ studiedToday: true, streakDays: 1 });
  });
});
