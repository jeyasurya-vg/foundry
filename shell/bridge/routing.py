"""Channel-per-stream routing (Part 5.1): map a project or department to its own chat/topic
instead of everything going to one operator chat.

Reads a small JSON file (`company/bridge_channels.json`, gitignored local config, same
treatment as `company/ledger.db` — see `company/bridge_channels.example.json` for the
documented shape to copy). `thread_id`, when set, is Telegram's `message_thread_id` — real
per-topic routing once the operator's own Telegram supergroup has topics enabled, which is
their own group setup, not a new credential.
"""

import json
from pathlib import Path

DEFAULT_PATH = "company/bridge_channels.json"


class RouteNotFound(Exception):
    pass


class ChannelRouter:
    def __init__(self, path=DEFAULT_PATH):
        self.path = Path(path)
        self._config = self._load()

    def _load(self):
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def resolve(self, project_id=None, department=None):
        """Returns (chat_id, thread_id). Project routes win over department routes; both
        fall back to `default`. Raises RouteNotFound if nothing resolves — callers that
        already have an explicit --chat-id should never call this at all."""
        if project_id:
            route = self._config.get("projects", {}).get(project_id)
            if route:
                return route.get("chat_id"), route.get("thread_id")

        if department:
            route = self._config.get("departments", {}).get(department)
            if route:
                return route.get("chat_id"), route.get("thread_id")

        default = self._config.get("default")
        if default and default.get("chat_id"):
            return default.get("chat_id"), default.get("thread_id")

        raise RouteNotFound(
            f"no channel route for project={project_id!r} department={department!r}, and no "
            f"'default' configured in {self.path}. Pass --chat-id explicitly, or add a route."
        )
