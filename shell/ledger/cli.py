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
from .projects import Portfolio


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


def cmd_resume(ledger, args):
    ticket = ledger.resumable(project_id=args.project)
    if ticket is None:
        _print({"resumable": False})
        return
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


def cmd_project_add(portfolio, args):
    project_id = portfolio.add_project(
        project_id=args.id, name=args.name, brief=args.brief,
        priority=args.priority, wip_limit=args.wip_limit, repo_path=args.repo_path,
    )
    _print(portfolio.get_project(project_id))


def _project_transition(method_name, extra_args=()):
    def handler(portfolio, args):
        try:
            method = getattr(portfolio, method_name)
            kwargs = {name: getattr(args, name) for name in extra_args}
            state = method(args.project_id, args.rationale, **kwargs)
        except (KeyError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        _print({"id": args.project_id, "state": state})
    return handler


def cmd_project_shelve(portfolio, args):
    try:
        state = portfolio.shelve(args.project_id, reason=args.reason, revive_when=args.revive_when)
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    _print({"id": args.project_id, "state": state})


def cmd_project_list(portfolio, args):
    _print(portfolio.list_projects(state=args.state))


def cmd_project_shelf(portfolio, args):
    _print(portfolio.shelf())


def cmd_project_status(portfolio, args):
    project = portfolio.get_project(args.project_id)
    if project is None:
        print(f"no such project: {args.project_id}", file=sys.stderr)
        sys.exit(1)
    _print({
        "project": project,
        "events": portfolio.list_events(args.project_id),
        "releases": portfolio.list_releases(args.project_id),
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

    p_resume = sub.add_parser("resume", help="find a ticket orphaned mid-run (session died while it was `running`)")
    p_resume.add_argument("--project")
    p_resume.set_defaults(func=cmd_resume)

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
    p_status.set_defaults(func=cmd_status, backend="ledger")

    for p in (p_add, p_next, p_resume, p_ckpt, p_status):
        p.set_defaults(backend="ledger")

    p_project = sub.add_parser("project", help="portfolio: manage project lifecycle (addendum Part 11)")
    proj_sub = p_project.add_subparsers(dest="project_command", required=True)

    pp_add = proj_sub.add_parser("add", help="propose a new project")
    pp_add.add_argument("--id", required=True)
    pp_add.add_argument("--name", required=True)
    pp_add.add_argument("--brief", required=True)
    pp_add.add_argument("--priority", type=int, default=5)
    pp_add.add_argument("--wip-limit", type=int, default=3)
    pp_add.add_argument("--repo-path")
    pp_add.set_defaults(func=cmd_project_add, backend="portfolio")

    for name, method in (
        ("greenlight", "greenlight"), ("reject", "reject"), ("start", "start"),
        ("maintain", "maintain"), ("revive", "revive"), ("archive", "archive"),
    ):
        pp = proj_sub.add_parser(name, help=f"transition a project via `{method}`")
        pp.add_argument("project_id")
        pp.add_argument("--rationale", required=True)
        pp.set_defaults(func=_project_transition(method), backend="portfolio")

    pp_ship = proj_sub.add_parser("ship", help="active -> shipped, optionally recording a release")
    pp_ship.add_argument("project_id")
    pp_ship.add_argument("--rationale", required=True)
    pp_ship.add_argument("--version")
    pp_ship.add_argument("--tag")
    pp_ship.add_argument("--changelog-path")
    pp_ship.set_defaults(
        func=_project_transition("ship", extra_args=("version", "tag", "changelog_path")),
        backend="portfolio",
    )

    pp_shelve = proj_sub.add_parser("shelve", help="stop deliberately (reason + revival condition mandatory)")
    pp_shelve.add_argument("project_id")
    pp_shelve.add_argument("--reason", required=True)
    pp_shelve.add_argument("--revive-when", required=True)
    pp_shelve.set_defaults(func=cmd_project_shelve, backend="portfolio")

    pp_list = proj_sub.add_parser("list", help="list projects, optionally filtered by state")
    pp_list.add_argument("--state")
    pp_list.set_defaults(func=cmd_project_list, backend="portfolio")

    pp_shelf = proj_sub.add_parser("shelf", help="list every shelved project (for the periodic shelf review)")
    pp_shelf.set_defaults(func=cmd_project_shelf, backend="portfolio")

    pp_status = proj_sub.add_parser("status", help="one project's full history")
    pp_status.add_argument("project_id")
    pp_status.set_defaults(func=cmd_project_status, backend="portfolio")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    obj = Portfolio(args.db) if args.backend == "portfolio" else Ledger(args.db)
    try:
        args.func(obj, args)
    finally:
        obj.close()


if __name__ == "__main__":
    main()
