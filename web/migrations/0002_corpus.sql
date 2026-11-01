CREATE TABLE corpus_versions (
  version TEXT PRIMARY KEY,
  service TEXT NOT NULL,
  built_at TEXT NOT NULL,
  source_commit TEXT,
  documents INTEGER NOT NULL,
  chunks INTEGER NOT NULL,
  loaded_at INTEGER NOT NULL,
  is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1))
);

CREATE TABLE corpus_documents (
  id TEXT PRIMARY KEY,
  service TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('cmg', 'csm', 'med')),
  number TEXT NOT NULL,
  title TEXT NOT NULL,
  section TEXT NOT NULL,
  scope TEXT NOT NULL CHECK (scope IN ('all', 'mixed', 'icp', 'pacer')),
  version_date TEXT,
  checksum TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (source_type = 'guideline'),
  licence TEXT NOT NULL,
  attribution TEXT NOT NULL,
  source_url TEXT NOT NULL,
  corpus_version TEXT NOT NULL
);

CREATE INDEX corpus_documents_kind ON corpus_documents (service, kind, section);

CREATE TABLE corpus_document_bodies (
  document_id TEXT NOT NULL REFERENCES corpus_documents (id) ON DELETE CASCADE,
  view TEXT NOT NULL CHECK (view IN ('ap', 'ap_pacer', 'icp', 'icp_pacer')),
  markdown TEXT NOT NULL,
  PRIMARY KEY (document_id, view)
);

CREATE TABLE corpus_chunks (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  heading TEXT NOT NULL,
  text TEXT NOT NULL,
  embed_text TEXT NOT NULL,
  vis_ap INTEGER NOT NULL CHECK (vis_ap IN (0, 1)),
  vis_ap_pacer INTEGER NOT NULL CHECK (vis_ap_pacer IN (0, 1)),
  vis_icp INTEGER NOT NULL CHECK (vis_icp IN (0, 1)),
  vis_icp_pacer INTEGER NOT NULL CHECK (vis_icp_pacer IN (0, 1)),
  source_type TEXT NOT NULL CHECK (source_type = 'guideline'),
  licence TEXT NOT NULL,
  attribution TEXT NOT NULL,
  corpus_version TEXT NOT NULL,
  embedded_at INTEGER,
  retired_at INTEGER
);

CREATE INDEX corpus_chunks_document ON corpus_chunks (document_id, ordinal);
CREATE INDEX corpus_chunks_pending ON corpus_chunks (embedded_at) WHERE embedded_at IS NULL AND retired_at IS NULL;
CREATE INDEX corpus_chunks_retired ON corpus_chunks (retired_at) WHERE retired_at IS NOT NULL;
