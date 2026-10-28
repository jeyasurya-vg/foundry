"""Structured actions an approval can apply automatically once it resolves `approved` — the
actual approval points `docs/BRIDGE.md` named as missing: release-to-main (`Portfolio.ship`)
and deletes (`Portfolio.shelve`/`Portfolio.archive`).

`Portfolio.ship`/`shelve`/`archive` stay directly callable exactly as before — nothing here
changes their behaviour or makes them require a bridge. This is an additional, optional gated
path: a ticket/project action is described as `(kind, payload)`, requested through the
bridge, and only actually applied by `apply()` once a human has approved it.
"""

import json

from ..ledger.projects import Portfolio


def _apply_ship(portfolio, payload):
    return portfolio.ship(**payload)


def _apply_shelve(portfolio, payload):
    return portfolio.shelve(**payload)


def _apply_archive(portfolio, payload):
    return portfolio.archive(**payload)


ACTIONS = {
    "portfolio.ship": _apply_ship,
    "portfolio.shelve": _apply_shelve,
    "portfolio.archive": _apply_archive,
}


def apply(action_kind, payload, ledger_db_path):
    """Opens a `Portfolio` against `ledger_db_path`, applies the named action, closes it.
    `payload` may be a dict already, or a JSON string (as stored in `approvals.action_payload`).
    Raises `KeyError` for an unknown `action_kind` — callers should only ever apply a kind
    they themselves put into the registry below."""
    if action_kind not in ACTIONS:
        raise KeyError(f"unknown action kind: {action_kind!r} (known: {sorted(ACTIONS)})")
    if isinstance(payload, str):
        payload = json.loads(payload)

    portfolio = Portfolio(ledger_db_path)
    try:
        return ACTIONS[action_kind](portfolio, payload)
    finally:
        portfolio.close()
