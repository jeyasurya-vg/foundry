"""UsageTracker: a self-logged ledger of quota observations across providers.

There is no compliant way to poll live "how much quota is left" numbers for a
Claude Pro/Max subscription, a ChatGPT Codex subscription, or (in general)
whatever a cloud provider's dashboard shows — either the provider has no
public API for it, or the only route is reusing a subscription OAuth session
token outside its official client, which this project's COMPLIANCE.md
forbids for Claude and which we hold to the same standard for every provider.

So this tracks usage the same way the ticket ledger tracks tickets: as an
append-only log of observations, with the arithmetic (time until reset, is
this stale) computed locally. You feed it what each provider's own UI already
shows you (Claude Code's `/usage` output, a Codex CLI status line, an Ollama
dashboard); it remembers it and gives you one place to check across all of
them.

Session boundary events (from a Claude Code SessionStart/SessionEnd hook) are
logged separately and used only as a rough elapsed-time proxy alongside the
most recent real observation — never as a substitute for one.
"""

from datetime import datetime, timezone

from . import db
from .providers import get_provider, is_stub, valid_window


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(ts):
    if ts is None:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class UsageTracker:
    def __init__(self, db_path=db.DEFAULT_DB_PATH):
        self.conn = db.connect(db_path)

    def close(self):
        self.conn.close()

    # -- recording -------------------------------------------------------

    def record(
        self,
        provider,
        window,
        remaining=None,
        limit_desc=None,
        reset_at=None,
        source="manual",
        note=None,
    ):
        get_provider(provider)  # raises KeyError for unknown providers
        if not valid_window(provider, window):
            raise ValueError(
                f"{provider!r} has no {window!r} window "
                f"(has: {get_provider(provider)['windows']})"
            )
        if remaining is not None and not (0.0 <= remaining <= 1.0):
            raise ValueError("remaining must be a fraction between 0.0 and 1.0")

        self.conn.execute(
            """INSERT INTO observations
               (provider, window, remaining, limit_desc, reset_at, source, note, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (provider, window, remaining, limit_desc, reset_at, source, note, _now()),
        )
        self.conn.commit()

    def log_session_event(self, provider, event, session_id=None, cwd=None):
        if event not in ("start", "end"):
            raise ValueError("event must be 'start' or 'end'")
        get_provider(provider)
        self.conn.execute(
            """INSERT INTO sessions (provider, session_id, event, cwd, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (provider, session_id, event, cwd, _now()),
        )
        self.conn.commit()

    # -- reads -------------------------------------------------------------

    def latest(self, provider, window):
        row = self.conn.execute(
            """SELECT * FROM observations WHERE provider = ? AND window = ?
               ORDER BY recorded_at DESC LIMIT 1""",
            (provider, window),
        ).fetchone()
        return dict(row) if row else None

    def recent_sessions(self, provider, since=None):
        q = "SELECT * FROM sessions WHERE provider = ?"
        params = [provider]
        if since:
            q += " AND created_at >= ?"
            params.append(since)
        q += " ORDER BY created_at ASC"
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]

    def status(self, provider=None, now=None):
        now = now or _now()
        now_dt = _parse(now)
        providers = [provider] if provider else None
        from .providers import PROVIDERS

        names = providers or list(PROVIDERS)
        result = {}
        for name in names:
            meta = get_provider(name)
            windows = {}
            for window in meta["windows"]:
                obs = self.latest(name, window)
                entry = {"observed": obs is not None}
                if obs:
                    entry["remaining"] = obs["remaining"]
                    entry["limit_desc"] = obs["limit_desc"]
                    entry["reset_at"] = obs["reset_at"]
                    entry["recorded_at"] = obs["recorded_at"]
                    reset_dt = _parse(obs["reset_at"])
                    if reset_dt:
                        seconds = (reset_dt - now_dt).total_seconds()
                        entry["seconds_until_reset"] = seconds
                        entry["reset_has_passed"] = seconds <= 0
                windows[window] = entry
            result[name] = {
                "label": meta["label"],
                "status": meta["status"],
                "note": meta["note"] if is_stub(name) else None,
                "windows": windows,
            }
        return result
