CREATE TABLE IF NOT EXISTS shadow_runtime_days (
  commit_sha TEXT NOT NULL,
  runtime_date TEXT NOT NULL,
  deployment_mode TEXT NOT NULL CHECK(deployment_mode='SHADOW_ACCEPTANCE'),
  observed_at TEXT NOT NULL,
  PRIMARY KEY(commit_sha,runtime_date)
);
