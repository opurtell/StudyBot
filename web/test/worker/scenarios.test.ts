import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { retireStaleScenarios } from "../../src/worker/scenarios/bank";
import { scenarioScore, stageScore } from "../../src/shared/scenarios";
import { ALL, ICP_ONLY, seed, type Vis } from "./fixtures";
import { call, postJson, signIn } from "./helpers";

const S_AP = "cccccccccccccc01";
const S_AP_HARD = "cccccccccccccc02";
const S_ICP = "dddddddddddddd01";

function stages(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    ordinal: i + 1,
    reveal: `Findings ${i + 1}`,
    question: `Question ${i + 1}?`,
    focus: "assessment",
    rubric: [
      { point: "Critical point", critical: true, cites: [{ chunk_id: "ch_ap", document_id: "CMG_10_Diabetic", quote: "q1" }] },
      { point: "Point two", critical: false, cites: [{ chunk_id: "ch_ap", document_id: "CMG_10_Diabetic", quote: "q2" }] },
      { point: "Point three", critical: false, cites: [{ chunk_id: "ch_ap", document_id: "CMG_10_Diabetic", quote: "q3" }] },
    ],
  }));
}

async function addScenario(id: string, chunk: string, vis: Vis, opts: { difficulty?: string; category?: string; group?: string; stages?: number } = {}) {
  const doc = chunk === "ch_icp" ? "CMG_3A_RSI" : "CMG_10_Diabetic";
  await env.DB.batch([
    env.DB.prepare(
      `INSERT INTO scenario_bank (id, service, primary_document_id, category, patient_group, difficulty, title, dispatch_text,
         stages_json, gen_view, vis_ap, vis_ap_pacer, vis_icp, vis_icp_pacer, source_type, content_hash, prompt_version,
         model_id, check_model_id, corpus_version, created_at, updated_at)
       VALUES (?1, 'actas', ?2, ?3, ?4, ?5, 'Case ' || ?1, 'Dispatch ' || ?1, ?6, 'ap', ?7, ?8, ?9, ?10, 'guideline',
         'hash-' || ?1, 'scenario-1', 'lmstudio:w', 'lmstudio:c', 'v1', 0, 0)`,
    ).bind(id, doc, opts.category ?? "Medical", opts.group ?? "adult", opts.difficulty ?? "easy",
      JSON.stringify(stages(opts.stages ?? 2)), ...vis),
    env.DB.prepare(`INSERT INTO scenario_sources (scenario_id, chunk_id, document_id) VALUES (?1, ?2, ?3)`).bind(id, chunk, doc),
  ]);
}

async function openToEveryone() {
  await env.DB.prepare(`INSERT INTO app_flags (key, value, updated_at) VALUES ('scenarios_enabled', 'everyone', 0)`).run();
}

async function next(body: Record<string, unknown>, cookie?: string) {
  const res = await postJson("/api/scenarios/next", body, { cookie });
  return { res, body: (await res.json()) as { scenario: { id: string; stage: { ordinal: number } | null; stageCount: number } | null; exhausted: boolean; canRepeat?: boolean } };
}

afterEach(() => vi.restoreAllMocks());

beforeEach(async () => {
  await seed();
  await env.DB.batch(
    ["scenario_reports", "scenario_attempts", "user_scenario_seen", "scenario_sources", "scenario_bank"].map((t) =>
      env.DB.prepare(`DELETE FROM ${t}`),
    ),
  );
  await addScenario(S_AP, "ch_ap", ALL);
  await addScenario(S_AP_HARD, "ch_ap2", ALL, { difficulty: "hard", stages: 3, group: "paediatric" });
  await addScenario(S_ICP, "ch_icp", ICP_ONLY, { category: "Airway" });
});

describe("scoring", () => {
  it("needs every critical point and half the rest for correct", () => {
    const rubric = [{ critical: true }, { critical: false }, { critical: false }];
    expect(stageScore(rubric, [0, 1])).toBe("correct");
    expect(stageScore(rubric, [0])).toBe("partial");
    expect(stageScore(rubric, [1, 2])).toBe("incorrect");
    expect(scenarioScore(["correct", "correct"])).toBe("correct");
    expect(scenarioScore(["correct", "incorrect"])).toBe("partial");
    expect(scenarioScore(["incorrect", "incorrect", "correct"])).toBe("incorrect");
  });
});

describe("audience flag", () => {
  it("hides scenarios from everyone but admins until switched on", async () => {
    expect((await next({ view: "ap" })).res.status).toBe(404);
    const { email, cookie } = await signIn();
    expect((await next({ view: "ap" }, cookie)).res.status).toBe(404);
    await env.DB.prepare(`UPDATE users SET is_admin = 1 WHERE email = ?1`).bind(email).run();
    expect((await next({ view: "ap" }, cookie)).res.status).toBe(200);
    const flag = await postJson("/api/admin/scenarios/audience", { audience: "everyone" }, { cookie });
    expect(flag.status).toBe(200);
    expect((await next({ view: "ap" })).res.status).toBe(200);
  });
});

describe("serving", () => {
  beforeEach(openToEveryone);

  it("never gives an AP user an ICP-only scenario and returns only the first stage", async () => {
    const seen: string[] = [];
    for (let i = 0; i < 3; i += 1) {
      const { body } = await next({ view: "ap", exclude: seen });
      if (body.scenario) {
        expect(body.scenario.stage?.ordinal).toBe(1);
        expect(JSON.stringify(body.scenario)).not.toContain("Critical point");
        seen.push(body.scenario.id);
      }
    }
    expect(seen.sort()).toEqual([S_AP, S_AP_HARD]);
    expect((await next({ view: "ap", exclude: seen })).body).toMatchObject({ scenario: null, exhausted: true });
  });

  it("filters by category, difficulty, patient group and ICP only", async () => {
    expect((await next({ view: "ap", difficulty: "hard" })).body.scenario?.id).toBe(S_AP_HARD);
    expect((await next({ view: "ap", patientGroup: "paediatric" })).body.scenario?.id).toBe(S_AP_HARD);
    expect((await next({ view: "icp", category: "Airway" })).body.scenario?.id).toBe(S_ICP);
    expect((await next({ view: "icp", icpOnly: true })).body.scenario?.id).toBe(S_ICP);
    expect((await next({ view: "ap", icpOnly: true })).res.status).toBe(400);
    expect((await next({ view: "ap", difficulty: "brutal" })).res.status).toBe(400);
  });

  it("remembers what a signed-in user has seen and offers a repeat", async () => {
    const { cookie } = await signIn();
    const first = await next({ view: "ap", difficulty: "easy" }, cookie);
    expect(first.body.scenario?.id).toBe(S_AP);
    const again = await next({ view: "ap", difficulty: "easy" }, cookie);
    expect(again.body).toMatchObject({ scenario: null, exhausted: true, canRepeat: true });
    expect((await next({ view: "ap", difficulty: "easy", repeat: true }, cookie)).body.scenario?.id).toBe(S_AP);
  });

  it("reveals a stage's rubric with the next stage", async () => {
    const res = await postJson(`/api/scenarios/${S_AP}/stages/1/reveal`, { view: "ap" });
    const body = (await res.json()) as { rubric: { critical: boolean; cites: { quote: string }[] }[]; next: { ordinal: number } | null };
    expect(body.rubric[0]).toMatchObject({ critical: true, cites: [{ quote: "q1", chunkId: "ch_ap" }] });
    expect(body.next?.ordinal).toBe(2);
    const last = (await (await postJson(`/api/scenarios/${S_AP}/stages/2/reveal`, { view: "ap" })).json()) as { next: unknown };
    expect(last.next).toBeNull();
    expect((await postJson(`/api/scenarios/${S_ICP}/stages/1/reveal`, { view: "ap" })).status).toBe(404);
  });

  it("does not serve a scenario whose source chunk has gone, and the cron retires it", async () => {
    await env.DB.prepare(`UPDATE corpus_chunks SET retired_at = 1 WHERE id = 'ch_ap2'`).run();
    const { body } = await next({ view: "ap", difficulty: "hard" });
    expect(body.scenario).toBeNull();
    expect(await retireStaleScenarios(env.DB, 5)).toBe(1);
    const row = await env.DB.prepare(`SELECT status, status_reason FROM scenario_bank WHERE id = ?1`).bind(S_AP_HARD).first();
    expect(row).toMatchObject({ status: "retired", status_reason: "source_changed" });
  });

  it("lists option counts for the scope", async () => {
    const res = await call("/api/scenarios/options?view=ap");
    const body = (await res.json()) as { options: { category: string; difficulty: string; count: number }[] };
    expect(body.options.reduce((n, o) => n + o.count, 0)).toBe(2);
  });

  it("saves a signed-in attempt with server-side scoring", async () => {
    expect((await postJson(`/api/scenarios/${S_AP}/attempts`, { view: "ap", stages: [] })).status).toBe(401);
    const { cookie } = await signIn();
    const partialSend = await postJson(`/api/scenarios/${S_AP}/attempts`, { view: "ap", stages: [{ ordinal: 1, ticked: [0] }] }, { cookie });
    expect(partialSend.status).toBe(400);
    const res = await postJson(
      `/api/scenarios/${S_AP}/attempts`,
      { view: "ap", stages: [{ ordinal: 1, ticked: [0, 1], answer: "my answer" }, { ordinal: 2, ticked: [1, 2] }] },
      { cookie },
    );
    expect(await res.json()).toMatchObject({ score: "partial", stages: [{ ordinal: 1, score: "correct" }, { ordinal: 2, score: "incorrect" }] });
    const bad = await postJson(`/api/scenarios/${S_AP}/attempts`, { view: "ap", stages: [{ ordinal: 1, ticked: [9] }, { ordinal: 2, ticked: [] }] }, { cookie });
    expect(bad.status).toBe(400);
  });

  it("withdraws a scenario after two signed-in reports", async () => {
    for (let i = 0; i < 2; i += 1) {
      const { cookie } = await signIn();
      const res = await postJson(`/api/scenarios/${S_AP}/report`, { reason: "incorrect", stage: 1 }, { cookie });
      expect(res.status).toBe(200);
    }
    const row = await env.DB.prepare(`SELECT status FROM scenario_bank WHERE id = ?1`).bind(S_AP).first();
    expect(row).toMatchObject({ status: "flagged" });
    expect((await postJson(`/api/scenarios/${S_AP}/report`, { reason: "nope" })).status).toBe(400);
  });

  it("lets admins retire and restore", async () => {
    const { email, cookie } = await signIn();
    expect((await postJson(`/api/admin/scenarios/${S_AP}/status`, { status: "retired" }, { cookie })).status).toBe(403);
    await env.DB.prepare(`UPDATE users SET is_admin = 1 WHERE email = ?1`).bind(email).run();
    expect((await postJson(`/api/admin/scenarios/${S_AP}/status`, { status: "retired" }, { cookie })).status).toBe(200);
    expect((await next({ view: "ap", difficulty: "easy" })).body.scenario).toBeNull();
    const summary = (await (await call("/api/admin/scenarios", { cookie })).json()) as { byStatus: Record<string, number>; audience: string };
    expect(summary).toMatchObject({ byStatus: { retired: 1, active: 2 }, audience: "everyone" });
  });
});
