"""CLI for the Foundry usage tracker: record, status, providers, log-session.

    python -m shell.usage.cli record --provider claude --window session --remaining 0.58 --reset 2026-09-01T17:00:00Z
    python -m shell.usage.cli status [--provider claude]
    python -m shell.usage.cli providers
    python -m shell.usage.cli log-session --provider claude --event start [--session-id ...]

See docs/USAGE.md.
"""

import argparse
import json
import sys

from . import db
from .providers import PROVIDERS
from .tracker import UsageTracker


def _print(obj):
    print(json.dumps(obj, indent=2, default=str))


def cmd_record(tracker, args):
    try:
        tracker.record(
            provider=args.provider,
            window=args.window,
            remaining=args.remaining,
            limit_desc=args.limit_desc,
            reset_at=args.reset,
            source=args.source,
            note=args.note,
        )
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    _print(tracker.latest(args.provider, args.window))


def cmd_status(tracker, args):
    _print(tracker.status(provider=args.provider))


def cmd_providers(tracker, args):
    _print(PROVIDERS)


def cmd_log_session(tracker, args):
    try:
        tracker.log_session_event(
            provider=args.provider, event=args.event,
            session_id=args.session_id, cwd=args.cwd,
        )
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    _print({"provider": args.provider, "event": args.event, "logged": True})


def build_parser():
    parser = argparse.ArgumentParser(prog="foundry-usage")
    parser.add_argument("--db", default=db.DEFAULT_DB_PATH, help="path to the usage sqlite file")
    sub = parser.add_subparsers(dest="command", required=True)

    p_record = sub.add_parser("record", help="log a usage observation you read off a provider's own UI")
    p_record.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    p_record.add_argument("--window", required=True, help="e.g. session, weekly, monthly")
    p_record.add_argument("--remaining", type=float, help="fraction remaining, 0.0-1.0")
    p_record.add_argument("--limit-desc", help="human description of the raw limit, e.g. '45 messages'")
    p_record.add_argument("--reset", help="ISO8601 timestamp the window resets at")
    p_record.add_argument("--source", default="manual")
    p_record.add_argument("--note")
    p_record.set_defaults(func=cmd_record)

    p_status = sub.add_parser("status", help="show latest known usage across providers")
    p_status.add_argument("--provider", choices=sorted(PROVIDERS))
    p_status.set_defaults(func=cmd_status)

    p_providers = sub.add_parser("providers", help="list configured providers and their status")
    p_providers.set_defaults(func=cmd_providers)

    p_log = sub.add_parser("log-session", help="record a session start/end boundary (used by hooks)")
    p_log.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    p_log.add_argument("--event", required=True, choices=["start", "end"])
    p_log.add_argument("--session-id")
    p_log.add_argument("--cwd")
    p_log.set_defaults(func=cmd_log_session)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    tracker = UsageTracker(args.db)
    try:
        args.func(tracker, args)
    finally:
        tracker.close()


if __name__ == "__main__":
    main()
