CREATE TABLE question_bank (
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
  source_type TEXT NOT NULL CHECK (source_type = 'guideline'),
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
  updated_at INTEGER NOT NULL
);

CREATE INDEX question_bank_serve ON question_bank (service, status, document_id, difficulty);
CREATE INDEX question_bank_chunk ON question_bank (chunk_id);

CREATE TABLE user_question_seen (
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  question_id TEXT NOT NULL,
  first_seen_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL,
  PRIMARY KEY (user_id, question_id)
);

CREATE TABLE attempts (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  question_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('marked', 'revealed')),
  score TEXT CHECK (score IS NULL OR score IN ('correct', 'partial', 'incorrect')),
  user_answer TEXT,
  evaluation_json TEXT,
  elapsed_ms INTEGER,
  prompt_version TEXT,
  model_id TEXT,
  created_at INTEGER NOT NULL
);

CREATE INDEX attempts_user ON attempts (user_id, created_at);

CREATE TABLE usage_ledger (
  id TEXT PRIMARY KEY,
  user_id TEXT REFERENCES users (id) ON DELETE SET NULL,
  kind TEXT NOT NULL CHECK (kind IN ('gen', 'eval')),
  outcome TEXT NOT NULL CHECK (outcome IN ('ok', 'unreadable', 'error')),
  model_id TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  question_id TEXT,
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  tokens_thinking INTEGER NOT NULL DEFAULT 0,
  tokens_cached INTEGER NOT NULL DEFAULT 0,
  cost_usd_micros INTEGER NOT NULL DEFAULT 0,
  cache_hit INTEGER NOT NULL DEFAULT 0 CHECK (cache_hit IN (0, 1)),
  gateway_log_id TEXT,
  latency_ms INTEGER,
  created_at INTEGER NOT NULL
);

CREATE INDEX usage_ledger_day ON usage_ledger (kind, created_at);

CREATE TABLE question_reports (
  id TEXT PRIMARY KEY,
  question_id TEXT NOT NULL,
  user_id TEXT REFERENCES users (id) ON DELETE SET NULL,
  reporter_key TEXT NOT NULL,
  reason TEXT NOT NULL CHECK (reason IN ('incorrect', 'out_of_scope', 'unclear', 'not_in_source', 'other')),
  detail TEXT,
  created_at INTEGER NOT NULL,
  resolved_at INTEGER,
  UNIQUE (question_id, reporter_key)
);

CREATE INDEX question_reports_open ON question_reports (question_id) WHERE resolved_at IS NULL;

CREATE TABLE app_flags (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);
