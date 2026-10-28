"""Approval requests: the bridge's "killer feature" (Part 5.1).

Irreversible actions arrive as inline buttons: Approve / Deny / Approve and remember. This
store tracks the mechanical part — a request, its text, and its resolution — provider-
agnostic (Telegram today, Slack/Matrix/Discord whenever those are built read and write the
same table).

Three optional fields (all default `None`, so a plain `request(text, ...)` behaves exactly
as before): `agent` names which `plugin/agents/*.md` fence "Approve and remember" should
append to (`shell/bridge/fence.py`); `action_kind`/`action_payload` describe a structured
action (e.g. `"portfolio.ship"` + its kwargs as JSON) to apply automatically once the
request resolves `approved` (`shell/bridge/actions.py`). See docs/BRIDGE.md.
"""

import uuid
from datetime import datetime, timezone

from . import db

DEFAULT_DB_PATH = db.DEFAULT_DB_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApprovalStore:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.conn = db.connect(db_path)

    def close(self):
        self.conn.close()

    def request(self, text, ticket_id=None, project_id=None, request_id=None,
                agent=None, action_kind=None, action_payload=None):
        request_id = request_id or uuid.uuid4().hex[:12]
        self.conn.execute(
            """INSERT INTO approvals
               (request_id, text, ticket_id, project_id, status, remember, requested_at,
                agent, action_kind, action_payload)
               VALUES (?, ?, ?, ?, 'pending', 0, ?, ?, ?, ?)""",
            (request_id, text, ticket_id, project_id, _now(), agent, action_kind, action_payload),
        )
        self.conn.commit()
        return request_id

    def resolve(self, request_id, decision, remember=False):
        if decision not in ("approved", "denied"):
            raise ValueError("decision must be 'approved' or 'denied'")
        row = self.get(request_id)
        if row is None:
            raise KeyError(f"unknown approval request: {request_id}")
        if row["status"] != "pending":
            raise ValueError(f"approval request {request_id} was already resolved as {row['status']!r}")
        self.conn.execute(
            "UPDATE approvals SET status = ?, remember = ?, resolved_at = ? WHERE request_id = ?",
            (decision, int(remember), _now(), request_id),
        )
        self.conn.commit()
        return self.get(request_id)

    def get(self, request_id):
        row = self.conn.execute(
            "SELECT * FROM approvals WHERE request_id = ?", (request_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_pending(self):
        rows = self.conn.execute(
            "SELECT * FROM approvals WHERE status = 'pending' ORDER BY requested_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_remembered(self):
        rows = self.conn.execute(
            "SELECT * FROM approvals WHERE remember = 1 ORDER BY requested_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]
