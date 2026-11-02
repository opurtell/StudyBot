import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ALL, CHUNK_TEXT, seed } from "./fixtures";
import { call, postJson, signIn } from "./helpers";

const REF_ID = "LITFL_atrial_flutter";
const Q_REF = "ccccccccccccccc1";
const ATTRIBUTION = '"Atrial Flutter", LITFL ECG Library, licensed under CC BY-NC-SA 4.0.';

afterEach(() => vi.restoreAllMocks());

beforeEach(async () => {
  await seed();
  const db = env.DB;
  await db.batch([
    db.prepare(
      `INSERT INTO corpus_documents (id, service, kind, number, title, section, scope, checksum, source_type, licence,
         attribution, source_url, corpus_version)
       VALUES (?1, 'actas', 'ref', 'LITFL', 'Atrial Flutter', 'ECGs', 'all', 'sum', 'general_reference', 'CC BY-NC-SA 4.0',
         ?2, 'https://litfl.com/atrial-flutter-ecg-library/', 'v1')`,
    ).bind(REF_ID, ATTRIBUTION),
    ...["ap", "ap_pacer", "icp", "icp_pacer"].map((view) =>
      db.prepare(`INSERT INTO corpus_document_bodies (document_id, view, markdown) VALUES (?1, ?2, '## ECG features\n\nSaw-tooth waves.')`).bind(REF_ID, view),
    ),
    db.prepare(
      `INSERT INTO corpus_chunks (id, document_id, ordinal, heading, text, embed_text, vis_ap, vis_ap_pacer, vis_icp,
         vis_icp_pacer, source_type, licence, attribution, corpus_version)
       VALUES ('ch_ref', ?1, 0, 'ECG features', ?2, '[LITFL] ch_ref ' || ?2, 1, 1, 1, 1, 'general_reference',
         'CC BY-NC-SA 4.0', ?3, 'v1')`,
    ).bind(REF_ID, CHUNK_TEXT, ATTRIBUTION),
    db.prepare(
      `INSERT INTO question_bank (id, service, document_id, chunk_id, source_text, question_text, question_type, difficulty,
         category, source_citation, gen_view, vis_ap, vis_ap_pacer, vis_icp, vis_icp_pacer, source_type, licence,
         attribution, content_hash, prompt_version, model_id, corpus_version, origin, status, created_at, updated_at)
       SELECT ?1, 'actas', ?2, c.id, c.embed_text, 'What ECG features define atrial flutter?', 'recall', 'easy', 'ECGs',
         'LITFL ECG Library: Atrial Flutter', 'ap', ?3, ?4, ?5, ?6, 'general_reference', c.licence, c.attribution,
         'hash-ref', 'general-1', 'gemini-3.8-flash', 'v1', 'bank', 'active', 0, 0
       FROM corpus_chunks c WHERE c.id = 'ch_ref'`,
    ).bind(Q_REF, REF_ID, ...ALL),
  ]);
});

describe("general references", () => {
  it("are listed and readable under /api/references, not as guidelines", async () => {
    const list = (await (await call("/api/references")).json()) as { items: { id: string; kind: string }[] };
    expect(list.items).toEqual([expect.objectContaining({ id: REF_ID, kind: "ref" })]);
    const guidelines = (await (await call("/api/guidelines")).json()) as { items: { id: string }[] };
    expect(guidelines.items.map((i) => i.id)).not.toContain(REF_ID);
    const doc = (await (await call(`/api/references/${REF_ID}?view=ap`)).json()) as { licence: string; attribution: string };
    expect(doc).toMatchObject({ licence: "CC BY-NC-SA 4.0", attribution: ATTRIBUTION });
    expect((await call(`/api/guidelines/${REF_ID}`)).status).toBe(404);
  });

  it("serve bank questions with their licence and attribution", async () => {
    const next = (await (await postJson("/api/quiz/next", { view: "ap", kinds: ["ref"] })).json()) as {
      question: { id: string; citation: string } | null;
      canGenerate: boolean;
    };
    expect(next.question).toMatchObject({ id: Q_REF, citation: "LITFL ECG Library: Atrial Flutter" });
    const reveal = (await (await postJson(`/api/quiz/questions/${Q_REF}/reveal`, { view: "ap" })).json()) as Record<string, unknown>;
    expect(reveal).toMatchObject({ licence: "CC BY-NC-SA 4.0", attribution: ATTRIBUTION, sourceType: "general_reference" });
  });

  it("are never used for live generation", async () => {
    const { cookie } = await signIn();
    const spy = vi.spyOn(globalThis, "fetch");
    spy.mockClear();
    const next = (await (await postJson("/api/quiz/next", { view: "ap", kinds: ["ref"], exclude: [Q_REF] }, { cookie })).json()) as {
      canGenerate: boolean;
    };
    expect(next.canGenerate).toBe(false);
    const res = await postJson("/api/quiz/generate", { view: "ap", kinds: ["ref"] }, { cookie });
    expect(res.status).toBe(404);
    expect(((await res.json()) as { message: string }).message).toContain("only written from the ACTAS guidelines");
    expect(spy).not.toHaveBeenCalled();
  });

  it("are left out of the chunks offered for live generation across all topics", async () => {
    const { cookie } = await signIn();
    const spy = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      Response.json({
        candidates: [{ content: { parts: [{ text: JSON.stringify({ question_text: "What BGL defines hypoglycaemia?", question_type: "recall", source_citation: "ACTAS CMG 10", category: "Medical", source_index: 1 }) }] }, finishReason: "STOP" }],
        usageMetadata: { promptTokenCount: 10, candidatesTokenCount: 10 },
      }),
    );
    expect((await postJson("/api/quiz/generate", { view: "icp_pacer" }, { cookie })).status).toBe(200);
    const sent = String(spy.mock.calls[0]?.[1]?.body);
    expect(sent).not.toContain("ch_ref");
  });
});
