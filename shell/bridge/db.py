"""SQLite schema and connection helper for the bridge's approval requests."""

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS approvals (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id   TEXT NOT NULL UNIQUE,
  text         TEXT NOT NULL,
  ticket_id    TEXT,
  project_id   TEXT,
  status       TEXT NOT NULL DEFAULT 'pending',
  remember     INTEGER NOT NULL DEFAULT 0,
  requested_at TEXT NOT NULL,
  resolved_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
"""

DEFAULT_DB_PATH = "company/bridge.db"


def connect(db_path=DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
