CREATE TABLE user_settings (
  user_id TEXT PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
  qualification TEXT CHECK (qualification IS NULL OR qualification IN ('ap', 'icp')),
  pacer INTEGER NOT NULL DEFAULT 0 CHECK (pacer IN (0, 1)),
  excluded_sections TEXT NOT NULL DEFAULT '[]',
  excluded_documents TEXT NOT NULL DEFAULT '[]',
  updated_at INTEGER NOT NULL
);

CREATE INDEX attempts_user_question ON attempts (user_id, question_id, created_at);
