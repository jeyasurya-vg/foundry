"""SQLite schema and connection helper for the Foundry usage tracker.

See docs/USAGE.md for the design and why this is a self-logged ledger rather
than a live API poller.
"""

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS observations (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  provider    TEXT NOT NULL,
  window      TEXT NOT NULL,
  remaining   REAL,
  limit_desc  TEXT,
  reset_at    TEXT,
  source      TEXT NOT NULL DEFAULT 'manual',
  note        TEXT,
  recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  provider   TEXT NOT NULL,
  session_id TEXT,
  event      TEXT NOT NULL,
  cwd        TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_observations_provider_window
  ON observations(provider, window, recorded_at);
CREATE INDEX IF NOT EXISTS idx_sessions_provider
  ON sessions(provider, created_at);
"""

DEFAULT_DB_PATH = "company/usage.db"


def connect(db_path=DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
