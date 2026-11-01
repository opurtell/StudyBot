CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free')),
  is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
  quota_period TEXT NOT NULL,
  free_gen_used INTEGER NOT NULL DEFAULT 0 CHECK (free_gen_used >= 0),
  free_eval_used INTEGER NOT NULL DEFAULT 0 CHECK (free_eval_used >= 0),
  created_at INTEGER NOT NULL,
  last_sign_in_at INTEGER
);

CREATE TABLE login_tokens (
  token_hash TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  used_at INTEGER
);

CREATE INDEX login_tokens_email_created ON login_tokens (email, created_at);
CREATE INDEX login_tokens_expires ON login_tokens (expires_at);

CREATE TABLE sessions (
  id_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL
);

CREATE INDEX sessions_user ON sessions (user_id);
CREATE INDEX sessions_expires ON sessions (expires_at);
