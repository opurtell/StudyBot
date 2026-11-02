import { env } from "cloudflare:workers";

export type Vis = [number, number, number, number];
export const ALL: Vis = [1, 1, 1, 1];
export const ICP_ONLY: Vis = [0, 0, 1, 1];

export const CHUNK_TEXT = "x".repeat(250);

export async function seed() {
  const db = env.DB;
  const stmts = [
    "DELETE FROM question_reports",
    "DELETE FROM usage_ledger",
    "DELETE FROM attempts",
    "DELETE FROM user_question_seen",
    "DELETE FROM question_bank",
    "DELETE FROM app_flags",
    "DELETE FROM corpus_chunks",
    "DELETE FROM corpus_documents",
    "DELETE FROM corpus_versions",
  ].map((sql) => db.prepare(sql));
  stmts.push(
    db.prepare(
      `INSERT INTO corpus_versions (version, service, built_at, documents, chunks, loaded_at, is_current)
       VALUES ('v1', 'actas', '2026-11-01', 2, 3, 0, 1)`,
    ),
  );
  for (const [id, number, title, section] of [
    ["CMG_10_Diabetic", "10", "Diabetic Emergencies", "Medical"],
    ["CMG_3A_RSI", "3A", "Rapid Sequence Intubation", "Airway"],
  ]) {
    stmts.push(
      db
        .prepare(
          `INSERT INTO corpus_documents (id, service, kind, number, title, section, scope, checksum, source_type, licence,
             attribution, source_url, corpus_version)
           VALUES (?1, 'actas', 'cmg', ?2, ?3, ?4, 'all', 'sum', 'guideline', 'ACTAS public guidelines',
             'ACT Ambulance Service Clinical Management Guidelines', 'https://cmg.ambulance.act.gov.au', 'v1')`,
        )
        .bind(id, number, title, section),
    );
  }
  const chunk = (id: string, doc: string, vis: Vis) =>
    db
      .prepare(
        `INSERT INTO corpus_chunks (id, document_id, ordinal, heading, text, embed_text, vis_ap, vis_ap_pacer, vis_icp,
           vis_icp_pacer, source_type, licence, attribution, corpus_version)
         VALUES (?1, ?2, 0, 'H', ?3, '[ACTAS] ' || ?1 || ' ' || ?3, ?4, ?5, ?6, ?7, 'guideline', 'l', 'a', 'v1')`,
      )
      .bind(id, doc, CHUNK_TEXT, ...vis);
  stmts.push(chunk("ch_ap", "CMG_10_Diabetic", ALL), chunk("ch_ap2", "CMG_10_Diabetic", ALL), chunk("ch_icp", "CMG_3A_RSI", ICP_ONLY));
  await db.batch(stmts);
}

export async function addQuestion(id: string, chunkId: string, vis: Vis, opts: { difficulty?: string; status?: string } = {}) {
  const doc = chunkId === "ch_icp" ? "CMG_3A_RSI" : "CMG_10_Diabetic";
  await env.DB.prepare(
    `INSERT INTO question_bank (id, service, document_id, chunk_id, source_text, question_text, question_type, difficulty,
       category, source_citation, gen_view, vis_ap, vis_ap_pacer, vis_icp, vis_icp_pacer, source_type, licence, attribution,
       content_hash, prompt_version, model_id, corpus_version, origin, status, created_at, updated_at)
     SELECT ?1, 'actas', ?2, c.id, c.embed_text, 'Question ' || ?1, 'recall', ?3, 'Medical', 'ACTAS CMG 10', 'ap',
       ?4, ?5, ?6, ?7, 'guideline', 'l', 'a', 'hash-' || ?1, 'web-1', 'gemini-3.8-flash', 'v1', 'bank', ?8, 0, 0
     FROM corpus_chunks c WHERE c.id = ?9`,
  )
    .bind(id, doc, opts.difficulty ?? "easy", ...vis, opts.status ?? "active", chunkId)
    .run();
}

export const Q_AP = "aaaaaaaaaaaaaaa1";
export const Q_AP2 = "aaaaaaaaaaaaaaa2";
export const Q_ICP = "bbbbbbbbbbbbbbb1";

