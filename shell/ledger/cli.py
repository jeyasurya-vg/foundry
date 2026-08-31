"""CLI for the Foundry ledger: add, next, checkpoint, status.

    python -m shell.ledger.cli add --brief "..." --done-when "..."
    python -m shell.ledger.cli next
    python -m shell.ledger.cli checkpoint <id> --summary "..." --next-step "..." [--final]
    python -m shell.ledger.cli status [<id>]
"""

import argparse
import json
import sys

from .ledger import DEFAULT_DB_PATH, Ledger


def _print(obj):
    print(json.dumps(obj, indent=2, default=str))


def cmd_add(ledger, args):
    ticket_id = ledger.add_ticket(
        brief=args.brief,
        done_when=args.done_when,
        project_id=args.project,
        parent_id=args.parent_id,
        depends_on=args.depends_on,
        ticket_id=args.id,
        auto_queue=not args.no_auto_queue,
    )
    _print(ledger.get_ticket(ticket_id))


def cmd_next(ledger, args):
    ticket = ledger.next_ready(project_id=args.project)
    if ticket is None:
        _print({"ready": False})
        return
    ledger.claim(ticket["id"], assignee=args.assignee)
    ledger.start_running(ticket["id"])
    ticket = ledger.get_ticket(ticket["id"])
    ticket["last_checkpoint"] = ledger.last_checkpoint(ticket["id"])
    _print(ticket)


def cmd_checkpoint(ledger, args):
    if args.fail:
        state = ledger.fail(args.ticket_id)
        _print({"id": args.ticket_id, "state": state})
        return

    if args.blocked_until:
        state = ledger.block_quota(args.ticket_id, blocked_until=args.blocked_until)
        _print({"id": args.ticket_id, "state": state})
        return

    artifacts = json.loads(args.artifacts)
    step_no = ledger.checkpoint(args.ticket_id, args.summary, artifacts, args.next_step)
    state = ledger.advance_to_review(args.ticket_id) if args.final else ledger.resume_running(args.ticket_id)
    _print({"id": args.ticket_id, "step_no": step_no, "state": state})


def cmd_status(ledger, args):
    if args.ticket_id:
        ticket = ledger.get_ticket(args.ticket_id)
        if ticket is None:
            print(f"no such ticket: {args.ticket_id}", file=sys.stderr)
            sys.exit(1)
        _print({
            "ticket": ticket,
            "checkpoints": ledger.list_checkpoints(args.ticket_id),
            "events": ledger.list_events(args.ticket_id),
        })
        return

    _print({
        "summary": ledger.status_summary(project_id=args.project),
        "tickets": [
            {"id": t["id"], "state": t["state"], "project_id": t["project_id"], "brief": t["brief"]}
            for t in ledger.list_tickets(project_id=args.project)
        ],
    })


def build_parser():
    parser = argparse.ArgumentParser(prog="foundry-ledger")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="path to the ledger sqlite file")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="create a ticket")
    p_add.add_argument("--brief", required=True)
    p_add.add_argument("--done-when", required=True)
    p_add.add_argument("--project", default="default")
    p_add.add_argument("--parent-id")
    p_add.add_argument("--depends-on", nargs="*", default=[])
    p_add.add_argument("--id")
    p_add.add_argument("--no-auto-queue", action="store_true")
    p_add.set_defaults(func=cmd_add)

    p_next = sub.add_parser("next", help="claim and start the next ready ticket")
    p_next.add_argument("--project")
    p_next.add_argument("--assignee", default="engineer")
    p_next.set_defaults(func=cmd_next)

    p_ckpt = sub.add_parser("checkpoint", help="record a checkpoint / advance or pause a ticket")
    p_ckpt.add_argument("ticket_id")
    p_ckpt.add_argument("--summary")
    p_ckpt.add_argument("--artifacts", default="[]", help="JSON list of artifact paths/SHAs")
    p_ckpt.add_argument("--next-step")
    p_ckpt.add_argument("--final", action="store_true", help="this was the last step; move to review")
    p_ckpt.add_argument("--fail", action="store_true", help="the step failed; retry or mark dead")
    p_ckpt.add_argument("--blocked-until", help="ISO8601 timestamp; pause on a quota window instead of checkpointing")
    p_ckpt.set_defaults(func=cmd_checkpoint)

    p_status = sub.add_parser("status", help="show ticket or board status")
    p_status.add_argument("ticket_id", nargs="?")
    p_status.add_argument("--project")
    p_status.set_defaults(func=cmd_status)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    ledger = Ledger(args.db)
    try:
        args.func(ledger, args)
    finally:
        ledger.close()


if __name__ == "__main__":
    main()
