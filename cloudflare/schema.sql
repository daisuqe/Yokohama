CREATE TABLE IF NOT EXISTS scores (
  stage   TEXT    NOT NULL,
  id      TEXT    NOT NULL,
  name    TEXT    NOT NULL,
  score   INTEGER NOT NULL,
  level   INTEGER NOT NULL,
  updated TEXT,
  PRIMARY KEY (stage, id)
);
CREATE INDEX IF NOT EXISTS idx_scores_rank ON scores (stage, score DESC);
