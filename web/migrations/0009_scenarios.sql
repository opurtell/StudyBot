CREATE TABLE scenario_bank (
  id TEXT PRIMARY KEY,
  service TEXT NOT NULL,
  primary_document_id TEXT NOT NULL,
  category TEXT NOT NULL,
  patient_group TEXT NOT NULL CHECK (patient_group IN ('adult', 'paediatric', 'neonate', 'obstetric', 'older_adult')),
  difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
  title TEXT NOT NULL,
  dispatch_text TEXT NOT NULL,
  stages_json TEXT NOT NULL,
  gen_view TEXT NOT NULL CHECK (gen_view IN ('ap', 'ap_pacer', 'icp', 'icp_pacer')),
  vis_ap INTEGER NOT NULL CHECK (vis_ap IN (0, 1)),
  vis_ap_pacer INTEGER NOT NULL CHECK (vis_ap_pacer IN (0, 1)),
  vis_icp INTEGER NOT NULL CHECK (vis_icp IN (0, 1)),
  vis_icp_pacer INTEGER NOT NULL CHECK (vis_icp_pacer IN (0, 1)),
  source_type TEXT NOT NULL CHECK (source_type = 'guideline'),
  content_hash TEXT NOT NULL UNIQUE,
  prompt_version TEXT NOT NULL,
  model_id TEXT NOT NULL,
  check_model_id TEXT NOT NULL,
  corpus_version TEXT NOT NULL,
  reviewed_by TEXT,
  reviewed_at INTEGER,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'flagged', 'retired')),
  status_reason TEXT,
  rand_key REAL NOT NULL DEFAULT 0,
  times_served INTEGER NOT NULL DEFAULT 0,
  times_reported INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX scenario_bank_pick ON scenario_bank (service, status, category, difficulty, rand_key);

CREATE TRIGGER scenario_bank_rand_key AFTER INSERT ON scenario_bank
WHEN NEW.rand_key = 0
BEGIN
  UPDATE scenario_bank SET rand_key = (abs(random()) % 1000000000) / 1000000000.0 + 0.000000001 WHERE id = NEW.id;
END;

CREATE TABLE scenario_sources (
  scenario_id TEXT NOT NULL REFERENCES scenario_bank (id) ON DELETE CASCADE,
  chunk_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  PRIMARY KEY (scenario_id, chunk_id)
);

CREATE INDEX scenario_sources_chunk ON scenario_sources (chunk_id);

CREATE TABLE scenario_attempts (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  scenario_id TEXT NOT NULL,
  view TEXT NOT NULL CHECK (view IN ('ap', 'ap_pacer', 'icp', 'icp_pacer')),
  stage_results_json TEXT NOT NULL,
  score TEXT NOT NULL CHECK (score IN ('correct', 'partial', 'incorrect')),
  created_at INTEGER NOT NULL
);

CREATE INDEX scenario_attempts_user ON scenario_attempts (user_id, created_at);

CREATE TABLE user_scenario_seen (
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  scenario_id TEXT NOT NULL,
  first_seen_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL,
  PRIMARY KEY (user_id, scenario_id)
);

CREATE TABLE scenario_reports (
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  stage INTEGER,
  user_id TEXT REFERENCES users (id) ON DELETE SET NULL,
  reporter_key TEXT NOT NULL,
  reason TEXT NOT NULL CHECK (reason IN ('incorrect', 'out_of_scope', 'unclear', 'not_in_source', 'other')),
  detail TEXT,
  created_at INTEGER NOT NULL,
  resolved_at INTEGER,
  UNIQUE (scenario_id, reporter_key)
);

CREATE INDEX scenario_reports_open ON scenario_reports (scenario_id) WHERE resolved_at IS NULL;
CREATE INDEX scenario_reports_reporter ON scenario_reports (reporter_key, created_at);
