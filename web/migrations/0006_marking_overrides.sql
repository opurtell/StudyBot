CREATE TABLE marking_overrides (
  id TEXT PRIMARY KEY,
  attempt_id TEXT NOT NULL UNIQUE,
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  question_id TEXT NOT NULL,
  document_id TEXT,
  document_title TEXT,
  section TEXT,
  category TEXT,
  citation TEXT,
  question_origin TEXT,
  question_text TEXT,
  source_text TEXT,
  view TEXT CHECK (view IS NULL OR view IN ('ap', 'ap_pacer', 'icp', 'icp_pacer')),
  user_answer TEXT,
  model_score TEXT NOT NULL CHECK (model_score IN ('correct', 'partial', 'incorrect')),
  user_score TEXT NOT NULL CHECK (user_score IN ('correct', 'partial', 'incorrect')),
  direction TEXT NOT NULL CHECK (direction IN ('model_too_harsh', 'model_too_lenient')),
  evaluation_json TEXT NOT NULL,
  model_id TEXT,
  prompt_version TEXT,
  marked_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX marking_overrides_created ON marking_overrides (created_at);
CREATE INDEX marking_overrides_question ON marking_overrides (question_id);
