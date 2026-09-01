"""CLI for the Foundry messaging bridge.

    python -m shell.bridge.cli --allow ID [--allow ID2] send --chat-id ID --text "..."
    python -m shell.bridge.cli --allow ID request-approval --chat-id ID --text "..." [--ticket T] [--project P]
    python -m shell.bridge.cli --allow ID poll [--timeout 25]
    python -m shell.bridge.cli list-pending

`--allow` takes the operator ID(s) directly; `FOUNDRY_BRIDGE_ALLOWLIST` (comma-separated) is
read as a fallback so you don't have to pass it on every invocation. See docs/BRIDGE.md.
"""

import argparse
import json
import os
import sys

from .approvals import ApprovalStore, DEFAULT_DB_PATH as APPROVALS_DB
from .base import InboundCallback
from .env import load_dotenv
from .telegram import TelegramBridge


def _print(obj):
    print(json.dumps(obj, indent=2, default=str))


def _resolve_allowlist(args):
    if args.allow:
        return args.allow
    env_list = os.environ.get("FOUNDRY_BRIDGE_ALLOWLIST", "")
    return [x.strip() for x in env_list.split(",") if x.strip()]


def _bridge(args):
    allowlist = _resolve_allowlist(args)
    if not allowlist:
        print(
            "No allowlist configured. Pass --allow <id> or set FOUNDRY_BRIDGE_ALLOWLIST.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        return TelegramBridge(allowlist=allowlist)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


def cmd_send(args):
    bridge = _bridge(args)
    try:
        _print(bridge.send(args.chat_id, args.text))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


def cmd_request_approval(args):
    bridge = _bridge(args)
    store = ApprovalStore(args.db)
    try:
        request_id = store.request(args.text, ticket_id=args.ticket, project_id=args.project)
        bridge.send_approval_request(args.chat_id, args.text, request_id)
        _print({"request_id": request_id})
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    finally:
        store.close()


def cmd_poll(args):
    bridge = _bridge(args)
    store = ApprovalStore(args.db)
    try:
        events = bridge.poll(timeout=args.timeout)
        results = []
        for event in events:
            if isinstance(event, InboundCallback):
                resolved = store.resolve(event.request_id, event.decision, remember=event.remember)
                bridge.answer_callback(event.callback_query_id, text=f"Recorded: {event.decision}")
                results.append({"type": "approval", **resolved})
            else:
                results.append({
                    "type": "message", "user_id": event.user_id,
                    "chat_id": event.chat_id, "text": event.text,
                })
        _print(results)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    finally:
        store.close()


def cmd_list_pending(args):
    store = ApprovalStore(args.db)
    try:
        _print(store.list_pending())
    finally:
        store.close()


def build_parser():
    parser = argparse.ArgumentParser(prog="foundry-bridge")
    parser.add_argument("--db", default=APPROVALS_DB, help="path to the approvals sqlite file")
    parser.add_argument(
        "--allow", action="append",
        help="an operator ID allowed to use the bridge; repeat for more than one",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_send = sub.add_parser("send", help="send a plain message")
    p_send.add_argument("--chat-id", required=True)
    p_send.add_argument("--text", required=True)
    p_send.set_defaults(func=cmd_send)

    p_req = sub.add_parser("request-approval", help="send a message with Approve/Deny/Approve-and-remember buttons")
    p_req.add_argument("--chat-id", required=True)
    p_req.add_argument("--text", required=True)
    p_req.add_argument("--ticket")
    p_req.add_argument("--project")
    p_req.set_defaults(func=cmd_request_approval)

    p_poll = sub.add_parser("poll", help="one long-poll cycle; resolves any approval button presses")
    p_poll.add_argument("--timeout", type=int, default=25)
    p_poll.set_defaults(func=cmd_poll)

    p_pending = sub.add_parser("list-pending", help="list approval requests still awaiting a decision")
    p_pending.set_defaults(func=cmd_list_pending)

    return parser


def main(argv=None):
    load_dotenv()
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
