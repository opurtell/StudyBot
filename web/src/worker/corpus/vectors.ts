import type { CorpusView, DocumentKind } from "./repo";

export const EMBEDDING_MODEL = "@cf/baai/bge-base-en-v1.5";
export const EMBEDDING_DIMENSIONS = 768;
export const EMBED_BATCH = 50;

export interface Embedder {
  run(model: string, input: { text: string[] }): Promise<unknown>;
}

export interface VectorStore {
  upsert(vectors: VectorizeVector[]): Promise<unknown>;
  deleteByIds(ids: string[]): Promise<unknown>;
  query(vector: number[], options: VectorizeQueryOptions): Promise<VectorizeMatches>;
}

export interface VectorEnv {
  DB: D1Database;
  AI?: unknown;
  VECTORIZE?: unknown;
}

export interface SyncResult {
  available: boolean;
  embedded: number;
  removed: number;
  pending: number;
}

interface PendingRow {
  id: string;
  document_id: string;
  kind: DocumentKind;
  embed_text: string;
  corpus_version: string;
  vis_ap: number;
  vis_ap_pacer: number;
  vis_icp: number;
  vis_icp_pacer: number;
}

function bindings(env: VectorEnv): { ai: Embedder; index: VectorStore } | null {
  if (!env.AI || !env.VECTORIZE) return null;
  return { ai: env.AI as Embedder, index: env.VECTORIZE as VectorStore };
}

export async function embed(ai: Embedder, texts: string[]): Promise<number[][]> {
  const out = (await ai.run(EMBEDDING_MODEL, { text: texts })) as { data?: number[][] };
  const data = out.data ?? [];
  if (data.length !== texts.length || data.some((v) => v.length !== EMBEDDING_DIMENSIONS)) {
    throw new Error(`Embedding model returned ${data.length} vectors for ${texts.length} texts`);
  }
  return data;
}

async function pendingCount(db: D1Database): Promise<number> {
  const row = await db
    .prepare(`SELECT COUNT(*) AS n FROM corpus_chunks WHERE embedded_at IS NULL AND retired_at IS NULL`)
    .first<{ n: number }>();
  return row?.n ?? 0;
}

export async function syncVectors(env: VectorEnv, now: number, limit = EMBED_BATCH): Promise<SyncResult> {
  const b = bindings(env);
  if (!b) return { available: false, embedded: 0, removed: 0, pending: await pendingCount(env.DB) };

  const { results: retired } = await env.DB.prepare(
    `SELECT id FROM corpus_chunks WHERE retired_at IS NOT NULL ORDER BY retired_at LIMIT ?1`,
  )
    .bind(limit)
    .all<{ id: string }>();
  if (retired.length > 0) {
    const ids = retired.map((r) => r.id);
    await b.index.deleteByIds(ids);
    await env.DB.prepare(`DELETE FROM corpus_chunks WHERE id IN (SELECT value FROM json_each(?1)) AND retired_at IS NOT NULL`)
      .bind(JSON.stringify(ids))
      .run();
  }

  const { results: rows } = await env.DB.prepare(
    `SELECT c.id, c.document_id, d.kind, c.embed_text, c.corpus_version, c.vis_ap, c.vis_ap_pacer, c.vis_icp, c.vis_icp_pacer
     FROM corpus_chunks c JOIN corpus_documents d ON d.id = c.document_id
     WHERE c.embedded_at IS NULL AND c.retired_at IS NULL
     ORDER BY c.document_id, c.ordinal LIMIT ?1`,
  )
    .bind(limit)
    .all<PendingRow>();
  if (rows.length > 0) {
    const vectors = await embed(
      b.ai,
      rows.map((r) => r.embed_text),
    );
    await b.index.upsert(
      rows.map((r, i) => ({
        id: r.id,
        values: vectors[i] ?? [],
        metadata: {
          document_id: r.document_id,
          kind: r.kind,
          corpus_version: r.corpus_version,
          vis_ap: r.vis_ap === 1,
          vis_ap_pacer: r.vis_ap_pacer === 1,
          vis_icp: r.vis_icp === 1,
          vis_icp_pacer: r.vis_icp_pacer === 1,
        },
      })),
    );
    await env.DB.prepare(`UPDATE corpus_chunks SET embedded_at = ?1 WHERE id IN (SELECT value FROM json_each(?2))`)
      .bind(now, JSON.stringify(rows.map((r) => r.id)))
      .run();
  }

  return { available: true, embedded: rows.length, removed: retired.length, pending: await pendingCount(env.DB) };
}

export interface SearchHit {
  chunkId: string;
  documentId: string;
  title: string;
  number: string;
  kind: DocumentKind;
  heading: string;
  text: string;
  score: number;
}

export async function searchCorpus(env: VectorEnv, query: string, view: CorpusView, topK = 5): Promise<SearchHit[] | null> {
  const b = bindings(env);
  if (!b) return null;
  const [vector] = await embed(b.ai, [query]);
  const { matches } = await b.index.query(vector ?? [], { topK, filter: { [`vis_${view}`]: true } });
  if (matches.length === 0) return [];
  const { results } = await env.DB.prepare(
    `SELECT c.id, c.document_id, c.heading, c.text, d.title, d.number, d.kind
     FROM corpus_chunks c JOIN corpus_documents d ON d.id = c.document_id
     WHERE c.id IN (SELECT value FROM json_each(?1)) AND c.retired_at IS NULL AND c.vis_${view} = 1`,
  )
    .bind(JSON.stringify(matches.map((m) => m.id)))
    .all<{ id: string; document_id: string; heading: string; text: string; title: string; number: string; kind: DocumentKind }>();
  const byId = new Map(results.map((r) => [r.id, r]));
  return matches.flatMap((m) => {
    const r = byId.get(m.id);
    return r
      ? [{ chunkId: r.id, documentId: r.document_id, title: r.title, number: r.number, kind: r.kind, heading: r.heading, text: r.text, score: m.score }]
      : [];
  });
}
