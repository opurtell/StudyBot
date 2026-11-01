export const CORPUS_SERVICE = "actas";
export const VIEWS = ["ap", "ap_pacer", "icp", "icp_pacer"] as const;
export type CorpusView = (typeof VIEWS)[number];
export type DocumentKind = "cmg" | "csm" | "med";
export const DEFAULT_VIEW: CorpusView = "icp_pacer";

export function parseView(value: string | undefined): CorpusView | null {
  if (value === undefined || value === "") return DEFAULT_VIEW;
  return (VIEWS as readonly string[]).includes(value) ? (value as CorpusView) : null;
}

export interface DocumentSummary {
  id: string;
  kind: DocumentKind;
  number: string;
  title: string;
  section: string;
  scope: "all" | "mixed" | "icp" | "pacer";
  versionDate: string | null;
}

export interface DocumentDetail extends DocumentSummary {
  view: CorpusView;
  markdown: string;
  checksum: string;
  attribution: string;
  licence: string;
  sourceUrl: string;
  corpusVersion: string;
}

interface DocumentRow {
  id: string;
  kind: DocumentKind;
  number: string;
  title: string;
  section: string;
  scope: DocumentSummary["scope"];
  version_date: string | null;
}

interface DetailRow extends DocumentRow {
  markdown: string | null;
  checksum: string;
  attribution: string;
  licence: string;
  source_url: string;
  corpus_version: string;
}

const collator = new Intl.Collator("en-AU", { numeric: true, sensitivity: "base" });

function toSummary(row: DocumentRow): DocumentSummary {
  return {
    id: row.id,
    kind: row.kind,
    number: row.number,
    title: row.title,
    section: row.section,
    scope: row.scope,
    versionDate: row.version_date,
  };
}

export async function currentCorpusVersion(db: D1Database): Promise<string | null> {
  const row = await db
    .prepare(`SELECT version FROM corpus_versions WHERE service = ?1 AND is_current = 1`)
    .bind(CORPUS_SERVICE)
    .first<{ version: string }>();
  return row?.version ?? null;
}

export async function listDocuments(db: D1Database, kinds: DocumentKind[]): Promise<DocumentSummary[]> {
  const { results } = await db
    .prepare(
      `SELECT id, kind, number, title, section, scope, version_date FROM corpus_documents
       WHERE service = ?1 AND kind IN (SELECT value FROM json_each(?2))`,
    )
    .bind(CORPUS_SERVICE, JSON.stringify(kinds))
    .all<DocumentRow>();
  return results.map(toSummary).sort((a, b) => collator.compare(a.number, b.number) || collator.compare(a.title, b.title));
}

export async function getDocument(
  db: D1Database,
  id: string,
  kinds: DocumentKind[],
  view: CorpusView,
): Promise<DocumentDetail | null> {
  const row = await db
    .prepare(
      `SELECT d.id, d.kind, d.number, d.title, d.section, d.scope, d.version_date, d.checksum, d.attribution,
              d.licence, d.source_url, d.corpus_version, b.markdown
       FROM corpus_documents d
       LEFT JOIN corpus_document_bodies b ON b.document_id = d.id AND b.view = ?3
       WHERE d.id = ?1 AND d.service = ?2 AND d.kind IN (SELECT value FROM json_each(?4))`,
    )
    .bind(id, CORPUS_SERVICE, view, JSON.stringify(kinds))
    .first<DetailRow>();
  if (!row) return null;
  return {
    ...toSummary(row),
    view,
    markdown: row.markdown ?? "",
    checksum: row.checksum,
    attribution: row.attribution,
    licence: row.licence,
    sourceUrl: row.source_url,
    corpusVersion: row.corpus_version,
  };
}

export interface CorpusStatus {
  version: string | null;
  builtAt: string | null;
  sourceCommit: string | null;
  documents: number;
  chunks: number;
  embedded: number;
  pending: number;
  retired: number;
}

export async function corpusStatus(db: D1Database): Promise<CorpusStatus> {
  const [version, counts] = await db.batch([
    db
      .prepare(`SELECT version, built_at, source_commit FROM corpus_versions WHERE service = ?1 AND is_current = 1`)
      .bind(CORPUS_SERVICE),
    db.prepare(
      `SELECT
         (SELECT COUNT(*) FROM corpus_documents) AS documents,
         (SELECT COUNT(*) FROM corpus_chunks WHERE retired_at IS NULL) AS chunks,
         (SELECT COUNT(*) FROM corpus_chunks WHERE retired_at IS NULL AND embedded_at IS NOT NULL) AS embedded,
         (SELECT COUNT(*) FROM corpus_chunks WHERE retired_at IS NULL AND embedded_at IS NULL) AS pending,
         (SELECT COUNT(*) FROM corpus_chunks WHERE retired_at IS NOT NULL) AS retired`,
    ),
  ]);
  const v = version?.results[0] as { version: string; built_at: string; source_commit: string | null } | undefined;
  const n = counts?.results[0] as { documents: number; chunks: number; embedded: number; pending: number; retired: number };
  return {
    version: v?.version ?? null,
    builtAt: v?.built_at ?? null,
    sourceCommit: v?.source_commit ?? null,
    ...n,
  };
}
