CREATE TABLE corpus_document_bodies_backup AS SELECT * FROM corpus_document_bodies;

CREATE TABLE corpus_documents_new (
  id TEXT PRIMARY KEY,
  service TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('cmg', 'csm', 'med', 'ref')),
  number TEXT NOT NULL,
  title TEXT NOT NULL,
  section TEXT NOT NULL,
  scope TEXT NOT NULL CHECK (scope IN ('all', 'mixed', 'icp', 'pacer')),
  version_date TEXT,
  checksum TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (
    (kind IN ('cmg', 'csm', 'med') AND source_type = 'guideline')
    OR (kind = 'ref' AND source_type = 'general_reference')
  ),
  licence TEXT NOT NULL,
  attribution TEXT NOT NULL,
  source_url TEXT NOT NULL,
  corpus_version TEXT NOT NULL
);

INSERT INTO corpus_documents_new SELECT id, service, kind, number, title, section, scope, version_date, checksum,
  source_type, licence, attribution, source_url, corpus_version FROM corpus_documents;

DROP TABLE corpus_documents;

ALTER TABLE corpus_documents_new RENAME TO corpus_documents;

CREATE INDEX corpus_documents_kind ON corpus_documents (service, kind, section);

DELETE FROM corpus_document_bodies;

INSERT INTO corpus_document_bodies (document_id, view, markdown)
SELECT document_id, view, markdown FROM corpus_document_bodies_backup;

DROP TABLE corpus_document_bodies_backup;

CREATE TABLE corpus_chunks_new (
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
  source_type TEXT NOT NULL CHECK (source_type IN ('guideline', 'general_reference')),
  licence TEXT NOT NULL,
  attribution TEXT NOT NULL,
  corpus_version TEXT NOT NULL,
  embedded_at INTEGER,
  retired_at INTEGER
);

INSERT INTO corpus_chunks_new SELECT id, document_id, ordinal, heading, text, embed_text, vis_ap, vis_ap_pacer, vis_icp,
  vis_icp_pacer, source_type, licence, attribution, corpus_version, embedded_at, retired_at FROM corpus_chunks;

DROP TABLE corpus_chunks;

ALTER TABLE corpus_chunks_new RENAME TO corpus_chunks;

CREATE INDEX corpus_chunks_document ON corpus_chunks (document_id, ordinal);
CREATE INDEX corpus_chunks_pending ON corpus_chunks (embedded_at) WHERE embedded_at IS NULL AND retired_at IS NULL;
CREATE INDEX corpus_chunks_retired ON corpus_chunks (retired_at) WHERE retired_at IS NOT NULL;

CREATE TABLE question_bank_new (
  id TEXT PRIMARY KEY,
  service TEXT NOT NULL,
  document_id TEXT NOT NULL,
  chunk_id TEXT NOT NULL,
  source_text TEXT NOT NULL,
  question_text TEXT NOT NULL,
  question_type TEXT NOT NULL CHECK (question_type IN ('recall', 'definition', 'scenario', 'drug_dose')),
  difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
  category TEXT NOT NULL,
  source_citation TEXT NOT NULL,
  gen_view TEXT NOT NULL CHECK (gen_view IN ('ap', 'ap_pacer', 'icp', 'icp_pacer')),
  vis_ap INTEGER NOT NULL CHECK (vis_ap IN (0, 1)),
  vis_ap_pacer INTEGER NOT NULL CHECK (vis_ap_pacer IN (0, 1)),
  vis_icp INTEGER NOT NULL CHECK (vis_icp IN (0, 1)),
  vis_icp_pacer INTEGER NOT NULL CHECK (vis_icp_pacer IN (0, 1)),
  source_type TEXT NOT NULL CHECK (source_type IN ('guideline', 'general_reference')),
  licence TEXT NOT NULL,
  attribution TEXT NOT NULL,
  content_hash TEXT NOT NULL UNIQUE,
  prompt_version TEXT NOT NULL,
  model_id TEXT NOT NULL,
  corpus_version TEXT NOT NULL,
  origin TEXT NOT NULL CHECK (origin IN ('bank', 'live')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'flagged', 'retired')),
  status_reason TEXT,
  times_served INTEGER NOT NULL DEFAULT 0,
  times_reported INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  rand_key REAL NOT NULL DEFAULT 0
);

INSERT INTO question_bank_new SELECT id, service, document_id, chunk_id, source_text, question_text, question_type,
  difficulty, category, source_citation, gen_view, vis_ap, vis_ap_pacer, vis_icp, vis_icp_pacer, source_type, licence,
  attribution, content_hash, prompt_version, model_id, corpus_version, origin, status, status_reason, times_served,
  times_reported, created_at, updated_at, rand_key FROM question_bank;

DROP TABLE question_bank;

ALTER TABLE question_bank_new RENAME TO question_bank;

CREATE INDEX question_bank_serve ON question_bank (service, status, document_id, difficulty);
CREATE INDEX question_bank_chunk ON question_bank (chunk_id);
CREATE INDEX question_bank_rand ON question_bank (service, status, rand_key);

CREATE TRIGGER question_bank_rand_key AFTER INSERT ON question_bank
WHEN NEW.rand_key = 0
BEGIN
  UPDATE question_bank SET rand_key = (abs(random()) % 1000000000) / 1000000000.0 + 0.000000001 WHERE id = NEW.id;
END;
