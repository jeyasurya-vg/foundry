"""The Foundry portfolio: project lifecycle state machine.

See docs/PORTFOLIO.md and blueprint addendum Part 11. A project is metadata layered on top of
the ticket ledger — `tickets.project_id` has no foreign key into `projects.id`, deliberately:
Phase 1 tickets work with a bare `project_id` string and no `projects` row at all (the default
`"default"` project_id from Phase 1 never needs a row here unless you want one). Adding a
`projects` entry is opt-in enrichment, not a requirement to create a ticket.
"""

from datetime import datetime, timezone

from . import db
from .ledger import DEFAULT_DB_PATH

# Legal transitions, keyed by current state. A transition not listed here is rejected.
PROJECT_TRANSITIONS = {
    "proposed":   {"greenlit", "rejected"},
    "greenlit":   {"active", "shelved"},
    "active":     {"shipped", "shelved"},
    "shipped":    {"maintained", "shelved"},
    "maintained": {"shelved"},
    "shelved":    {"revived", "archived"},
    "revived":    {"active"},
    "archived":   set(),
    "rejected":   set(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Portfolio:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.conn = db.connect(db_path)

    def close(self):
        self.conn.close()

    # -- creation ------------------------------------------------------------

    def add_project(self, project_id, name, brief, priority=5, wip_limit=3, repo_path=None):
        now = _now()
        self.conn.execute(
            """INSERT INTO projects
               (id, name, state, brief, repo_path, priority, wip_limit, created_at, updated_at)
               VALUES (?, ?, 'proposed', ?, ?, ?, ?, ?, ?)""",
            (project_id, name, brief, repo_path, priority, wip_limit, now, now),
        )
        self._log_event(project_id, None, "proposed", "project proposed")
        self.conn.commit()
        return project_id

    # -- state machine ---------------------------------------------------------

    def _transition(self, project_id, to_state, rationale, actor=None, **fields):
        if not rationale or not rationale.strip():
            raise ValueError("rationale is mandatory for every portfolio transition")
        row = self.get_project(project_id)
        if row is None:
            raise KeyError(f"unknown project: {project_id}")
        from_state = row["state"]
        allowed = PROJECT_TRANSITIONS.get(from_state, set())
        if to_state not in allowed:
            raise ValueError(
                f"illegal project transition for {project_id}: {from_state} -> {to_state} "
                f"(allowed: {sorted(allowed) or 'none, terminal state'})"
            )

        fields["state"] = to_state
        fields["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?",
            (*fields.values(), project_id),
        )
        self._log_event(project_id, from_state, to_state, rationale, actor=actor)
        self.conn.commit()
        return to_state

    def greenlight(self, project_id, rationale, actor=None):
        return self._transition(project_id, "greenlit", rationale, actor=actor)

    def reject(self, project_id, rationale, actor=None):
        return self._transition(project_id, "rejected", rationale, actor=actor)

    def start(self, project_id, rationale, actor=None):
        return self._transition(project_id, "active", rationale, actor=actor)

    def ship(self, project_id, rationale, version=None, tag=None, changelog_path=None, actor=None):
        state = self._transition(project_id, "shipped", rationale, actor=actor, shipped_at=_now())
        if version:
            self.add_release(project_id, version, tag=tag, changelog_path=changelog_path)
        return state

    def maintain(self, project_id, rationale, actor=None):
        return self._transition(project_id, "maintained", rationale, actor=actor)

    def shelve(self, project_id, reason, revive_when, actor=None):
        """Shelving is a first-class action, not an abandonment (Part 11.3).

        `reason` and `revive_when` are both mandatory, independent of the generic `rationale`
        check in `_transition` — this is the one transition the addendum singles out as
        requiring more than a one-line rationale.
        """
        if not reason or not reason.strip():
            raise ValueError("shelve requires a reason (Part 11.3, requirement 1)")
        if not revive_when or not revive_when.strip():
            raise ValueError("shelve requires a revival condition (Part 11.3, requirement 2)")
        return self._transition(
            project_id, "shelved", rationale=reason, actor=actor,
            shelved_at=_now(), shelve_reason=reason, revive_when=revive_when,
        )

    def revive(self, project_id, rationale, actor=None):
        return self._transition(
            project_id, "revived", rationale, actor=actor,
            shelved_at=None, shelve_reason=None,
        )

    def archive(self, project_id, rationale, actor=None):
        return self._transition(project_id, "archived", rationale, actor=actor)

    # -- releases --------------------------------------------------------------

    def add_release(self, project_id, version, tag=None, changelog_path=None):
        self.conn.execute(
            """INSERT INTO releases (project_id, version, tag, changelog_path, released_at)
               VALUES (?, ?, ?, ?, ?)""",
            (project_id, version, tag, changelog_path, _now()),
        )
        self.conn.commit()

    # -- reads -------------------------------------------------------------

    def get_project(self, project_id):
        row = self.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

    def list_projects(self, state=None):
        q = "SELECT * FROM projects"
        params = []
        if state:
            q += " WHERE state = ?"
            params.append(state)
        q += " ORDER BY created_at ASC"
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]

    def list_events(self, project_id):
        rows = self.conn.execute(
            "SELECT * FROM project_events WHERE project_id = ? ORDER BY id ASC", (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def list_releases(self, project_id):
        rows = self.conn.execute(
            "SELECT * FROM releases WHERE project_id = ? ORDER BY released_at ASC", (project_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def shelf(self):
        """Every shelved project, for the periodic shelf-review job (Part 11.3)."""
        return self.list_projects(state="shelved")

    def _log_event(self, project_id, from_state, to_state, rationale, actor=None):
        self.conn.execute(
            """INSERT INTO project_events
               (project_id, from_state, to_state, rationale, actor, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, from_state, to_state, rationale, actor, _now()),
        )
