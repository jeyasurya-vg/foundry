"""The Foundry ticket ledger: state machine, checkpoints, and dependency-aware scheduling.

State lives on disk, never in a session. See docs/LEDGER.md for the full state diagram and
the rationale behind it.
"""

import json
import uuid
from datetime import datetime, timezone

from . import db

DEFAULT_DB_PATH = "company/ledger.db"

# Legal transitions, keyed by current state. A transition not listed here is rejected.
TRANSITIONS = {
    "draft":         {"queued"},
    "queued":        {"claimed"},
    "claimed":       {"running"},
    "running":       {"checkpointed", "blocked_quota", "failed"},
    "checkpointed":  {"running", "review"},
    "blocked_quota": {"queued"},
    "review":        {"done", "rejected"},
    "rejected":      {"queued"},
    "failed":        {"queued", "dead"},
    "done":          set(),
    "dead":          set(),
}

MAX_ATTEMPTS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Ledger:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.conn = db.connect(db_path)

    def close(self):
        self.conn.close()

    # -- creation ----------------------------------------------------------

    def add_ticket(
        self,
        brief,
        done_when,
        project_id="default",
        parent_id=None,
        depends_on=None,
        ticket_id=None,
        auto_queue=True,
    ):
        ticket_id = ticket_id or f"t-{uuid.uuid4().hex[:8]}"
        now = _now()
        self.conn.execute(
            """INSERT INTO tickets
               (id, project_id, parent_id, stage, state, brief, done_when,
                attempts, created_at, updated_at)
               VALUES (?, ?, ?, 'intake', 'draft', ?, ?, 0, ?, ?)""",
            (ticket_id, project_id, parent_id, brief, done_when, now, now),
        )
        for dep in depends_on or []:
            self.conn.execute(
                "INSERT OR IGNORE INTO deps (ticket_id, depends_on) VALUES (?, ?)",
                (ticket_id, dep),
            )
        self._log_event(ticket_id, project_id, "created", {"brief": brief})
        self.conn.commit()

        if auto_queue:
            self.queue(ticket_id)
        return ticket_id

    # -- state machine -------------------------------------------------------

    def _transition(self, ticket_id, to_state, **fields):
        row = self.get_ticket(ticket_id)
        if row is None:
            raise KeyError(f"unknown ticket: {ticket_id}")
        from_state = row["state"]
        allowed = TRANSITIONS.get(from_state, set())
        if to_state not in allowed:
            raise ValueError(
                f"illegal transition for {ticket_id}: {from_state} -> {to_state} "
                f"(allowed: {sorted(allowed) or 'none, terminal state'})"
            )

        fields["state"] = to_state
        fields["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(
            f"UPDATE tickets SET {set_clause} WHERE id = ?",
            (*fields.values(), ticket_id),
        )
        self._log_event(ticket_id, row["project_id"], f"{from_state}->{to_state}")
        self.conn.commit()
        return to_state

    def queue(self, ticket_id):
        return self._transition(ticket_id, "queued")

    def claim(self, ticket_id, assignee):
        if not self._deps_satisfied(ticket_id):
            raise RuntimeError(f"{ticket_id} has unmet dependencies")
        return self._transition(ticket_id, "claimed", assignee=assignee)

    def start_running(self, ticket_id, session_id=None):
        return self._transition(ticket_id, "running", session_id=session_id)

    def checkpoint(self, ticket_id, summary, artifacts, next_step):
        row = self.get_ticket(ticket_id)
        if row is None:
            raise KeyError(f"unknown ticket: {ticket_id}")
        step_no = self.conn.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()[0] + 1
        self.conn.execute(
            """INSERT INTO checkpoints
               (ticket_id, project_id, step_no, summary, artifacts, next_step, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ticket_id, row["project_id"], step_no, summary, json.dumps(artifacts), next_step, _now()),
        )
        self.conn.commit()
        self._transition(ticket_id, "checkpointed")
        return step_no

    def resume_running(self, ticket_id):
        return self._transition(ticket_id, "running")

    def advance_to_review(self, ticket_id):
        return self._transition(ticket_id, "review")

    def block_quota(self, ticket_id, blocked_until):
        return self._transition(
            ticket_id, "blocked_quota", blocked_until=blocked_until, assignee=None
        )

    def release_expired_blocks(self, now=None):
        now = now or _now()
        rows = self.conn.execute(
            "SELECT id FROM tickets WHERE state = 'blocked_quota' AND blocked_until <= ?",
            (now,),
        ).fetchall()
        released = []
        for (ticket_id,) in rows:
            self._transition(ticket_id, "queued", blocked_until=None)
            released.append(ticket_id)
        return released

    def fail(self, ticket_id):
        row = self.get_ticket(ticket_id)
        attempts = row["attempts"] + 1
        self._transition(ticket_id, "failed", attempts=attempts)
        next_state = "dead" if attempts >= MAX_ATTEMPTS else "queued"
        return self._transition(ticket_id, next_state)

    def approve(self, ticket_id):
        return self._transition(ticket_id, "done")

    def reject(self, ticket_id, reason=None):
        state = self._transition(ticket_id, "rejected")
        if reason:
            self._log_event(ticket_id, self.get_ticket(ticket_id)["project_id"], "reject_reason", {"reason": reason})
        return state

    def requeue(self, ticket_id):
        return self._transition(ticket_id, "queued")

    # -- reads ---------------------------------------------------------------

    def get_ticket(self, ticket_id):
        row = self.conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return dict(row) if row else None

    def list_tickets(self, project_id=None, state=None):
        q = "SELECT * FROM tickets"
        clauses, params = [], []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if state:
            clauses.append("state = ?")
            params.append(state)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at ASC"
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]

    def list_checkpoints(self, ticket_id):
        rows = self.conn.execute(
            "SELECT * FROM checkpoints WHERE ticket_id = ? ORDER BY step_no ASC", (ticket_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def list_events(self, ticket_id):
        rows = self.conn.execute(
            "SELECT * FROM events WHERE ticket_id = ? ORDER BY id ASC", (ticket_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def last_checkpoint(self, ticket_id):
        row = self.conn.execute(
            "SELECT * FROM checkpoints WHERE ticket_id = ? ORDER BY step_no DESC LIMIT 1",
            (ticket_id,),
        ).fetchone()
        return dict(row) if row else None

    def resumable(self, project_id=None):
        """The most recently touched `running` ticket, if any.

        A ticket sits in `running` between checkpoints. If the session driving it dies there
        (killed mid-step, crashed, closed), the ticket is orphaned: `next_ready` will never
        offer it again because it isn't `queued`. This is how a fresh session finds it and
        picks the ticket back up from its last checkpoint, per docs/LEDGER.md Phase 3.
        """
        q = "SELECT id FROM tickets WHERE state = 'running'"
        params = []
        if project_id:
            q += " AND project_id = ?"
            params.append(project_id)
        q += " ORDER BY updated_at DESC LIMIT 1"
        row = self.conn.execute(q, params).fetchone()
        return self.get_ticket(row[0]) if row else None

    def next_ready(self, project_id=None):
        q = "SELECT id FROM tickets WHERE state = 'queued'"
        params = []
        if project_id:
            q += " AND project_id = ?"
            params.append(project_id)
        q += " ORDER BY created_at ASC"
        for (ticket_id,) in self.conn.execute(q, params).fetchall():
            if self._deps_satisfied(ticket_id):
                return self.get_ticket(ticket_id)
        return None

    def status_summary(self, project_id=None):
        q = "SELECT state, COUNT(*) as n FROM tickets"
        params = []
        if project_id:
            q += " WHERE project_id = ?"
            params.append(project_id)
        q += " GROUP BY state"
        return {row["state"]: row["n"] for row in self.conn.execute(q, params).fetchall()}

    def _deps_satisfied(self, ticket_id):
        dep_ids = [
            r[0] for r in self.conn.execute(
                "SELECT depends_on FROM deps WHERE ticket_id = ?", (ticket_id,)
            ).fetchall()
        ]
        if not dep_ids:
            return True
        placeholders = ",".join("?" for _ in dep_ids)
        n_done = self.conn.execute(
            f"SELECT COUNT(*) FROM tickets WHERE id IN ({placeholders}) AND state = 'done'",
            dep_ids,
        ).fetchone()[0]
        return n_done == len(dep_ids)

    def _log_event(self, ticket_id, project_id, kind, payload=None):
        self.conn.execute(
            "INSERT INTO events (ticket_id, project_id, kind, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, project_id, kind, json.dumps(payload) if payload is not None else None, _now()),
        )
