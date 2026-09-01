"""SQLite schema and connection helper for the Foundry ledger.

See docs/LEDGER.md for the state machine this schema supports.
"""

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tickets (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL DEFAULT 'default',
  parent_id     TEXT,
  stage         TEXT NOT NULL DEFAULT 'intake',
  state         TEXT NOT NULL DEFAULT 'draft',
  assignee      TEXT,
  branch        TEXT,
  session_id    TEXT,
  brief         TEXT NOT NULL,
  done_when     TEXT NOT NULL,
  attempts      INTEGER NOT NULL DEFAULT 0,
  blocked_until TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id  TEXT NOT NULL REFERENCES tickets(id),
  project_id TEXT NOT NULL,
  step_no    INTEGER NOT NULL,
  summary    TEXT NOT NULL,
  artifacts  TEXT NOT NULL,
  next_step  TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deps (
  ticket_id  TEXT NOT NULL,
  depends_on TEXT NOT NULL,
  PRIMARY KEY (ticket_id, depends_on)
);

CREATE TABLE IF NOT EXISTS events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id  TEXT,
  project_id TEXT,
  kind       TEXT NOT NULL,
  payload    TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  state         TEXT NOT NULL DEFAULT 'proposed',
  brief         TEXT NOT NULL,
  repo_path     TEXT,
  priority      INTEGER NOT NULL DEFAULT 5,
  wip_limit     INTEGER NOT NULL DEFAULT 3,
  budget_share  REAL NOT NULL DEFAULT 0.0,
  shipped_at    TEXT,
  shelved_at    TEXT,
  shelve_reason TEXT,
  revive_when   TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  from_state TEXT,
  to_state   TEXT NOT NULL,
  rationale  TEXT NOT NULL,
  actor      TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS releases (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id     TEXT NOT NULL,
  version        TEXT NOT NULL,
  tag            TEXT,
  changelog_path TEXT,
  released_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tickets_state ON tickets(state);
CREATE INDEX IF NOT EXISTS idx_tickets_project ON tickets(project_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_ticket ON checkpoints(ticket_id);
CREATE INDEX IF NOT EXISTS idx_deps_ticket ON deps(ticket_id);
CREATE INDEX IF NOT EXISTS idx_projects_state ON projects(state);
CREATE INDEX IF NOT EXISTS idx_project_events_project ON project_events(project_id);
CREATE INDEX IF NOT EXISTS idx_releases_project ON releases(project_id);
"""


def connect(db_path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
