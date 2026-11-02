ALTER TABLE question_bank ADD COLUMN rand_key REAL NOT NULL DEFAULT 0;

UPDATE question_bank SET rand_key = (abs(random()) % 1000000000) / 1000000000.0 + 0.000000001;

CREATE INDEX question_bank_rand ON question_bank (service, status, rand_key);

CREATE TRIGGER question_bank_rand_key AFTER INSERT ON question_bank
WHEN NEW.rand_key = 0
BEGIN
  UPDATE question_bank SET rand_key = (abs(random()) % 1000000000) / 1000000000.0 + 0.000000001 WHERE id = NEW.id;
END;

CREATE TABLE daily_usage (
  day INTEGER NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('gen', 'eval')),
  calls INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, kind)
);

INSERT INTO daily_usage (day, kind, calls)
SELECT created_at - (created_at % 86400000), kind, COUNT(*) FROM usage_ledger GROUP BY 1, 2;

CREATE TRIGGER usage_ledger_daily AFTER INSERT ON usage_ledger
BEGIN
  INSERT INTO daily_usage (day, kind, calls) VALUES (NEW.created_at - (NEW.created_at % 86400000), NEW.kind, 1)
  ON CONFLICT (day, kind) DO UPDATE SET calls = calls + 1;
END;

CREATE INDEX question_reports_reporter ON question_reports (reporter_key, created_at);
