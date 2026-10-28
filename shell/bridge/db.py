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

# Columns added after the original schema above. Each is appended with a plain `ALTER TABLE`,
# guarded against "duplicate column" so this stays idempotent against an existing local
# `company/bridge.db` from before these fields existed — same no-ORM-migration style as the
# rest of this codebase (there's no migration framework anywhere in `shell/`).
ADDED_COLUMNS = [
    ("agent", "TEXT"),            # which plugin/agent's fence "approve and remember" updates
    ("action_kind", "TEXT"),      # e.g. "portfolio.ship" - what to apply once approved
    ("action_payload", "TEXT"),   # JSON kwargs for that action
]

DEFAULT_DB_PATH = "company/bridge.db"


def _apply_column_migrations(conn):
    for name, sql_type in ADDED_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE approvals ADD COLUMN {name} {sql_type}")
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise


def connect(db_path=DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    _apply_column_migrations(conn)
    conn.commit()
    return conn
