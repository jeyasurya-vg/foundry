"""The autonomous scheduler loop (Part 3.4).

Intended to run on a timer (every ~60s per the blueprint) in a process that owns exactly one
runner. Concurrency defaults to 1 (compliance rule 4): `runner.busy()` gates everything.
"""

import json
from datetime import datetime, timedelta, timezone

from ..runners.base import ResumePacket
from .fairshare import next_ticket as _select_next_ticket


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _resume_packet(ledger, ticket):
    last = ledger.last_checkpoint(ticket["id"])
    return ResumePacket(
        ticket_id=ticket["id"],
        brief=ticket["brief"],
        done_when=ticket["done_when"],
        last_checkpoint_summary=last["summary"] if last else None,
        next_step=last["next_step"] if last else None,
        artifacts=json.loads(last["artifacts"]) if last else [],
        session_id=ticket.get("session_id"),
    )


def execute(ledger, runner, ticket, notify=print):
    """Runs exactly one ticket for exactly one step. Mirrors Part 3.4's `execute()`, adapted
    to this repo's actual Ledger API (which has no generic `transition()` — each transition
    is its own named method).

    On success, this does **not** force the ticket to `checkpointed` itself: the runner's own
    dispatched agent is expected to have called `shell.ledger.cli checkpoint` as part of doing
    the work, exactly as in attended mode. If it didn't, the ticket is left `running` with no
    new checkpoint — which `Ledger.resumable()` will pick up on the very next tick. That's not
    a gap here; it's the same orphan-recovery path Phase 3 already built.
    """
    ledger.start_running(ticket["id"], session_id=ticket.get("session_id"))
    packet = _resume_packet(ledger, ticket)
    result = runner.run(packet)

    if result.quota_exhausted:
        reset = result.reset_at or (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        ledger.block_quota(ticket["id"], blocked_until=reset)
        notify(f"{ticket['id']} paused on quota. Resumes {reset}. ({result.raw_message})")
        return ledger.get_ticket(ticket["id"])

    if not result.ok:
        state = ledger.fail(ticket["id"])
        notify(f"{ticket['id']} failed: {result.error}. New state: {state}.")
        return ledger.get_ticket(ticket["id"])

    notify(f"{ticket['id']} step completed by runner '{runner.name}'.")
    return ledger.get_ticket(ticket["id"])


def scheduler_tick(ledger, portfolio, runner, mode="balanced", window_consumed=None, notify=print):
    """One tick: release expired quota blocks, then — if the runner has headroom and isn't
    already busy — claim and run the next ticket the fair-share scheduler picks."""
    released = ledger.release_expired_blocks()
    for ticket_id in released:
        notify(f"{ticket_id} resumed: quota window reopened.")

    if runner.busy():
        return None

    ticket = _select_next_ticket(ledger, portfolio, runner, mode=mode, window_consumed=window_consumed)
    if ticket is None:
        return None

    ledger.claim(ticket["id"], assignee=runner.name)
    return execute(ledger, runner, ticket, notify=notify)
