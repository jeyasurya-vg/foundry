"""CLI for the Foundry messaging bridge.

    python -m shell.bridge.cli --allow ID [--allow ID2] send --chat-id ID --text "..."
    python -m shell.bridge.cli --allow ID send --project p-1 --text "..."
    python -m shell.bridge.cli --allow ID request-approval --chat-id ID --text "..." \
        [--ticket T] [--project P] [--agent engineer]
    python -m shell.bridge.cli --allow ID request-action --kind portfolio.ship \
        --project P --rationale "..." --text "ship P to main?" [--agent release]
    python -m shell.bridge.cli --allow ID poll [--timeout 25]
    python -m shell.bridge.cli list-pending

`--allow` takes the operator ID(s) directly; `FOUNDRY_BRIDGE_ALLOWLIST` (comma-separated) is
read as a fallback so you don't have to pass it on every invocation. `--chat-id` can be
replaced by `--project`/`--department`, resolved through `--channels` (channel-per-stream
routing, see docs/BRIDGE.md and shell/bridge/routing.py). See docs/BRIDGE.md.
"""

import argparse
import json
import os
import sys

from .actions import ACTIONS, apply as apply_action
from .approvals import ApprovalStore, DEFAULT_DB_PATH as APPROVALS_DB
from .base import InboundCallback
from .env import load_dotenv
from .fence import remember as fence_remember
from .routing import ChannelRouter, DEFAULT_PATH as CHANNELS_DEFAULT_PATH, RouteNotFound
from .telegram import TelegramBridge
from ..ledger.ledger import DEFAULT_DB_PATH as LEDGER_DEFAULT_DB


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


def _resolve_destination(args):
    """(chat_id, thread_id) from an explicit --chat-id, or --project/--department resolved
    through the channel router. Exits with a clear error if neither resolves."""
    if args.chat_id:
        return args.chat_id, None
    router = ChannelRouter(args.channels)
    try:
        return router.resolve(project_id=getattr(args, "project", None),
                               department=getattr(args, "department", None))
    except RouteNotFound as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


def cmd_send(args):
    bridge = _bridge(args)
    chat_id, thread_id = _resolve_destination(args)
    try:
        _print(bridge.send(chat_id, args.text, thread_id=thread_id))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


def cmd_request_approval(args):
    bridge = _bridge(args)
    chat_id, thread_id = _resolve_destination(args)
    store = ApprovalStore(args.db)
    try:
        request_id = store.request(
            args.text, ticket_id=args.ticket, project_id=args.project, agent=args.agent,
        )
        bridge.send_approval_request(chat_id, args.text, request_id, thread_id=thread_id)
        _print({"request_id": request_id})
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    finally:
        store.close()


def _build_action_payload(kind, args):
    if kind == "portfolio.ship":
        if not args.rationale:
            return None, "portfolio.ship requires --rationale"
        return {
            "project_id": args.project, "rationale": args.rationale,
            "version": args.version, "tag": args.tag, "changelog_path": args.changelog_path,
        }, None
    if kind == "portfolio.shelve":
        if not args.reason or not args.revive_when:
            return None, "portfolio.shelve requires --reason and --revive-when"
        return {"project_id": args.project, "reason": args.reason, "revive_when": args.revive_when}, None
    if kind == "portfolio.archive":
        if not args.rationale:
            return None, "portfolio.archive requires --rationale"
        return {"project_id": args.project, "rationale": args.rationale}, None
    return None, f"unknown --kind {kind!r} (known: {sorted(ACTIONS)})"


def cmd_request_action(args):
    payload, error = _build_action_payload(args.kind, args)
    if error:
        print(error, file=sys.stderr)
        sys.exit(1)

    bridge = _bridge(args)
    chat_id, thread_id = _resolve_destination(args)
    store = ApprovalStore(args.db)
    try:
        request_id = store.request(
            args.text, project_id=args.project, agent=args.agent,
            action_kind=args.kind, action_payload=json.dumps(payload),
        )
        bridge.send_approval_request(chat_id, args.text, request_id, thread_id=thread_id)
        _print({"request_id": request_id, "action_kind": args.kind, "action_payload": payload})
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
                entry = {"type": "approval", **resolved}

                if resolved["remember"] and resolved.get("agent"):
                    touched = fence_remember(resolved["agent"], resolved["text"], repo_root=args.repo_root)
                    entry["fence_updated"] = str(touched) if touched else None

                if resolved["status"] == "approved" and resolved.get("action_kind"):
                    try:
                        entry["action_result"] = apply_action(
                            resolved["action_kind"], resolved["action_payload"], args.ledger_db,
                        )
                    except (KeyError, ValueError) as exc:
                        entry["action_error"] = str(exc)

                results.append(entry)
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
    parser.add_argument("--ledger-db", default=LEDGER_DEFAULT_DB,
                         help="path to the ledger/portfolio sqlite file (for request-action / poll's auto-apply)")
    parser.add_argument("--repo-root", default=".",
                         help="repo root, for 'remember' fence updates (plugin/agents, .claude/agents)")
    parser.add_argument("--channels", default=CHANNELS_DEFAULT_PATH,
                         help="path to the channel-routing JSON file (see company/bridge_channels.example.json)")
    parser.add_argument(
        "--allow", action="append",
        help="an operator ID allowed to use the bridge; repeat for more than one",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_send = sub.add_parser("send", help="send a plain message")
    p_send.add_argument("--chat-id")
    p_send.add_argument("--project", help="resolve the chat via --channels instead of --chat-id")
    p_send.add_argument("--department", help="resolve the chat via --channels instead of --chat-id")
    p_send.add_argument("--text", required=True)
    p_send.set_defaults(func=cmd_send)

    p_req = sub.add_parser("request-approval", help="send a message with Approve/Deny/Approve-and-remember buttons")
    p_req.add_argument("--chat-id")
    p_req.add_argument("--project", help="resolve the chat via --channels instead of --chat-id")
    p_req.add_argument("--department", help="resolve the chat via --channels instead of --chat-id")
    p_req.add_argument("--text", required=True)
    p_req.add_argument("--ticket")
    p_req.add_argument("--agent", help="agent name whose fence 'approve and remember' should update")
    p_req.set_defaults(func=cmd_request_approval)

    p_act = sub.add_parser(
        "request-action",
        help="request approval for a structured action (portfolio.ship/shelve/archive) that applies itself once approved",
    )
    p_act.add_argument("--kind", required=True, choices=sorted(ACTIONS))
    p_act.add_argument("--project", required=True, help="project id the action applies to, and the channel-routing key")
    p_act.add_argument("--department", help="resolve the chat via --channels instead of --chat-id")
    p_act.add_argument("--chat-id")
    p_act.add_argument("--text", required=True)
    p_act.add_argument("--agent", help="agent name whose fence 'approve and remember' should update")
    p_act.add_argument("--rationale", help="required for portfolio.ship / portfolio.archive")
    p_act.add_argument("--version")
    p_act.add_argument("--tag")
    p_act.add_argument("--changelog-path")
    p_act.add_argument("--reason", help="required for portfolio.shelve")
    p_act.add_argument("--revive-when", help="required for portfolio.shelve")
    p_act.set_defaults(func=cmd_request_action)

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
