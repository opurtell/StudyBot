import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { app } from "../../src/worker/app";
import { EMBEDDING_DIMENSIONS, searchCorpus, syncVectors } from "../../src/worker/corpus/vectors";
import { call, freshIp, ORIGIN, signIn } from "./helpers";

afterEach(() => vi.restoreAllMocks());

const DOCS = [
  ["CMG_10_Diabetic_Emergencies", "cmg", "10", "Diabetic Emergencies", "Medical", "all"],
  ["CMG_3A_RSI", "cmg", "3A", "Rapid Sequence Intubation", "Airway", "icp"],
  ["CMG_2_Cardiac_Arrest", "cmg", "2", "Cardiac Arrest", "Cardiac", "mixed"],
  ["CMG_CSM.A01_Manual_Clearance", "csm", "CSM.A01", "Manual Clearance", "Clinical Skills", "all"],
  ["MED_03_Adrenaline", "med", "03", "Adrenaline", "Medicine", "mixed"],
] as const;

async function seedCorpus() {
  const db = env.DB;
  const stmts = [
    db.prepare(`DELETE FROM corpus_chunks`),
    db.prepare(`DELETE FROM corpus_documents`),
    db.prepare(`DELETE FROM corpus_versions`),
    db.prepare(
      `INSERT INTO corpus_versions (version, service, built_at, source_commit, documents, chunks, loaded_at, is_current)
       VALUES ('v1', 'actas', '2026-11-01T00:00:00+00:00', 'abc', 5, 3, 0, 1)`,
    ),
  ];
  for (const [id, kind, number, title, section, scope] of DOCS) {
    stmts.push(
      db
        .prepare(
          `INSERT INTO corpus_documents (id, service, kind, number, title, section, scope, version_date, checksum,
             source_type, licence, attribution, source_url, corpus_version)
           VALUES (?1, 'actas', ?2, ?3, ?4, ?5, ?6, NULL, 'sum', 'guideline', 'ACTAS public guidelines',
             'ACT Ambulance Service Clinical Management Guidelines', 'https://cmg.ambulance.act.gov.au', 'v1')`,
        )
        .bind(id, kind, number, title, section, scope),
    );
    for (const view of ["ap", "ap_pacer", "icp", "icp_pacer"]) {
      const body = scope === "icp" && view.startsWith("ap") ? "" : `# ${title}\n\n- ${view} text`;
      stmts.push(
        db.prepare(`INSERT INTO corpus_document_bodies (document_id, view, markdown) VALUES (?1, ?2, ?3)`).bind(id, view, body),
      );
    }
  }
  const chunk = (id: string, doc: string, ap: number, retired: number | null = null) =>
    db
      .prepare(
        `INSERT INTO corpus_chunks (id, document_id, ordinal, heading, text, embed_text, vis_ap, vis_ap_pacer, vis_icp,
           vis_icp_pacer, source_type, licence, attribution, corpus_version, retired_at)
         VALUES (?1, ?2, 0, 'Heading', 'Chunk ' || ?1, '[ACTAS] Chunk ' || ?1, ?3, ?3, 1, 1, 'guideline', 'l', 'a', 'v1', ?4)`,
      )
      .bind(id, doc, ap, retired);
  stmts.push(chunk("c1", "CMG_10_Diabetic_Emergencies", 1), chunk("c2", "CMG_3A_RSI", 0), chunk("c3", "MED_03_Adrenaline", 1));
  stmts.push(chunk("old", "CMG_10_Diabetic_Emergencies", 1, 5));
  await db.batch(stmts);
}

beforeEach(seedCorpus);

describe("guideline read API", () => {
  it("lists CMGs and skills in natural number order with public caching", async () => {
    const res = await call("/api/guidelines");
    expect(res.status).toBe(200);
    expect(res.headers.get("cache-control")).toBe("public, max-age=300");
    const body = (await res.json()) as { corpusVersion: string; items: { number: string; kind: string }[] };
    expect(body.corpusVersion).toBe("v1");
    expect(body.items.map((i) => i.number)).toEqual(["2", "3A", "10", "CSM.A01"]);
  });

  it("filters by kind and rejects unknown kinds", async () => {
    const res = await call("/api/guidelines?kind=csm");
    expect(((await res.json()) as { items: unknown[] }).items).toHaveLength(1);
    expect((await call("/api/guidelines?kind=notes")).status).toBe(400);
  });

  it("returns the body for the requested scope view", async () => {
    const res = await call("/api/guidelines/CMG_2_Cardiac_Arrest?view=ap");
    expect(await res.json()).toMatchObject({
      id: "CMG_2_Cardiac_Arrest",
      view: "ap",
      scope: "mixed",
      markdown: "# Cardiac Arrest\n\n- ap text",
      attribution: "ACT Ambulance Service Clinical Management Guidelines",
      corpusVersion: "v1",
    });
  });

  it("defaults to the full ICP and PACER view", async () => {
    const body = (await (await call("/api/guidelines/CMG_3A_RSI")).json()) as { view: string; markdown: string };
    expect(body.view).toBe("icp_pacer");
    expect(body.markdown).toContain("icp_pacer text");
  });

  it("gives an ICP-only guideline an empty AP body", async () => {
    const body = (await (await call("/api/guidelines/CMG_3A_RSI?view=ap")).json()) as { markdown: string; scope: string };
    expect(body).toMatchObject({ markdown: "", scope: "icp" });
  });

  it("rejects bad views and unknown ids, and keeps medicines out of the guideline routes", async () => {
    expect((await call("/api/guidelines/CMG_2_Cardiac_Arrest?view=paramedic")).status).toBe(400);
    expect((await call("/api/guidelines/CMG_404")).status).toBe(404);
    expect((await call("/api/guidelines/MED_03_Adrenaline")).status).toBe(404);
  });
});

describe("medication read API", () => {
  it("lists only medicine monographs", async () => {
    const body = (await (await call("/api/medications")).json()) as { items: { id: string }[] };
    expect(body.items.map((i) => i.id)).toEqual(["MED_03_Adrenaline"]);
  });

  it("returns a monograph and 404s for guidelines", async () => {
    expect((await call("/api/medications/MED_03_Adrenaline?view=icp")).status).toBe(200);
    expect((await call("/api/medications/CMG_2_Cardiac_Arrest")).status).toBe(404);
  });
});

function fakeBindings() {
  const upserts: VectorizeVector[] = [];
  const deleted: string[] = [];
  const ai = {
    run: vi.fn(async (_model: string, input: { text: string[] }) => ({
      data: input.text.map(() => Array.from({ length: EMBEDDING_DIMENSIONS }, () => 0.1)),
    })),
  };
  const index = {
    upsert: vi.fn(async (v: VectorizeVector[]) => {
      upserts.push(...v);
      return { mutationId: "m" };
    }),
    deleteByIds: vi.fn(async (ids: string[]) => {
      deleted.push(...ids);
      return { mutationId: "m" };
    }),
    query: vi.fn(async (_v: number[], opts: VectorizeQueryOptions) => ({
      count: 2,
      matches: [
        { id: "c2", score: 0.9 },
        { id: "c1", score: 0.8 },
      ].filter((m) => !(opts.filter && "vis_ap" in opts.filter && m.id === "c2")),
    })),
  };
  return { ai, index, upserts, deleted, env: { ...env, AI: ai, VECTORIZE: index } };
}

describe("vector sync", () => {
  it("does nothing without the AI and Vectorize bindings", async () => {
    expect(await syncVectors(env, 1)).toEqual({ available: false, embedded: 0, removed: 0, pending: 3 });
  });

  it("embeds pending chunks with scope metadata and removes retired ones", async () => {
    const fake = fakeBindings();
    const result = await syncVectors(fake.env, 1000);
    expect(result).toEqual({ available: true, embedded: 3, removed: 1, pending: 0 });
    expect(fake.deleted).toEqual(["old"]);
    const rsi = fake.upserts.find((v) => v.id === "c2");
    expect(rsi?.metadata).toMatchObject({ document_id: "CMG_3A_RSI", kind: "cmg", vis_ap: false, vis_icp: true });
    const left = await env.DB.prepare(`SELECT COUNT(*) AS n FROM corpus_chunks WHERE embedded_at IS NULL`).first<{ n: number }>();
    expect(left?.n).toBe(0);
    expect(await syncVectors(fake.env, 2000)).toEqual({ available: true, embedded: 0, removed: 0, pending: 0 });
  });

  it("works in batches", async () => {
    const fake = fakeBindings();
    expect((await syncVectors(fake.env, 1000, 2)).pending).toBe(1);
    expect((await syncVectors(fake.env, 1000, 2)).pending).toBe(0);
  });

  it("filters search hits by the viewer's scope", async () => {
    const fake = fakeBindings();
    const hits = await searchCorpus(fake.env, "hypoglycaemia", "ap");
    expect(fake.index.query).toHaveBeenCalledWith(expect.any(Array), { topK: 5, filter: { vis_ap: true } });
    expect(hits?.map((h) => h.chunkId)).toEqual(["c1"]);
    expect(await searchCorpus(env, "x", "ap")).toBeNull();
  });
});

describe("admin corpus API", () => {
  async function adminCookie() {
    const { cookie, email } = await signIn();
    await env.DB.prepare(`UPDATE users SET is_admin = 1 WHERE email = ?1`).bind(email.toLowerCase()).run();
    return cookie;
  }

  function adminCall(path: string, cookie: string, init: RequestInit = {}, bindings: object = env) {
    const headers = new Headers(init.headers);
    headers.set("cf-connecting-ip", freshIp());
    headers.set("cookie", cookie);
    return app.request(`${ORIGIN}${path}`, { ...init, headers }, bindings);
  }

  it("needs a signed-in admin", async () => {
    expect((await call("/api/admin/corpus")).status).toBe(401);
    const { cookie } = await signIn();
    expect((await call("/api/admin/corpus", { cookie })).status).toBe(403);
  });

  it("reports corpus status", async () => {
    const res = await adminCall("/api/admin/corpus", await adminCookie());
    expect(await res.json()).toMatchObject({ version: "v1", documents: 5, chunks: 3, pending: 3, retired: 1, vectorsAvailable: false });
  });

  it("syncs vectors on request", async () => {
    const fake = fakeBindings();
    const res = await adminCall(
      "/api/admin/corpus/sync",
      await adminCookie(),
      { method: "POST", headers: { origin: ORIGIN, "content-type": "application/json" }, body: "{}" },
      fake.env,
    );
    expect(await res.json()).toEqual({ available: true, embedded: 3, removed: 1, pending: 0 });
  });

  it("explains when vector search isn't configured", async () => {
    const res = await adminCall("/api/admin/corpus/search?q=glucose", await adminCookie());
    expect(res.status).toBe(503);
  });
});
