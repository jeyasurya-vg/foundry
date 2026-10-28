"""Telegram bridge: outbound long-polling only (Part 5.1 — "no inbound port, no tunnel, no
exposed service"). Talks to the Bot API directly via `urllib.request` — no third-party
Telegram SDK, matching this project's zero-runtime-dependency policy.

Gated by `TELEGRAM_BOT_TOKEN` (refuses to start without it — same "no fallback" discipline as
the autonomous runner's API-key gate) and a mandatory, non-empty allowlist: Part 5.1's
"single operator ID by default" only means something if there's always at least one ID
configured. An empty allowlist would silently accept everyone, the opposite of the feature.
"""

import json
import os
import urllib.request

from .allowlist import is_allowed
from .base import Bridge, InboundCallback, InboundMessage

API_URL = "https://api.telegram.org/bot{token}/{method}"


class TelegramBridge(Bridge):
    name = "telegram"

    def __init__(self, allowlist, token_env="TELEGRAM_BOT_TOKEN", request_fn=None):
        self.token_env = token_env
        self.allowlist = list(allowlist or [])
        if not self.allowlist:
            raise ValueError(
                "TelegramBridge requires a non-empty allowlist (Part 5.1: 'single operator "
                "ID by default'). An empty allowlist would silently accept everyone."
            )
        self._request = request_fn or self._http_request
        self._offset = None

    @property
    def token(self):
        return os.environ.get(self.token_env)

    def _call(self, method, payload):
        if not self.token:
            raise RuntimeError(
                f"{self.token_env} is not set. The bridge refuses to start without an "
                "explicit bot token — no fallback, no auto-detection."
            )
        url = API_URL.format(token=self.token, method=method)
        return self._request(url, payload)

    def _http_request(self, url, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)

    def send(self, chat_id, text, thread_id=None):
        payload = {"chat_id": chat_id, "text": text}
        if thread_id is not None:
            payload["message_thread_id"] = thread_id
        return self._call("sendMessage", payload)

    def send_approval_request(self, chat_id, text, request_id, thread_id=None):
        keyboard = {
            "inline_keyboard": [[
                {"text": "Approve", "callback_data": f"{request_id}:approved:0"},
                {"text": "Deny", "callback_data": f"{request_id}:denied:0"},
                {"text": "Approve and remember", "callback_data": f"{request_id}:approved:1"},
            ]]
        }
        payload = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
        if thread_id is not None:
            payload["message_thread_id"] = thread_id
        return self._call("sendMessage", payload)

    def answer_callback(self, callback_query_id, text=None):
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        return self._call("answerCallbackQuery", payload)

    def poll(self, timeout=25):
        params = {"timeout": timeout}
        if self._offset is not None:
            params["offset"] = self._offset
        result = self._call("getUpdates", params)

        events = []
        for update in result.get("result", []):
            self._offset = update["update_id"] + 1
            events.extend(self._parse_update(update))
        return events

    def _parse_update(self, update):
        if "message" in update:
            msg = update["message"]
            user_id = msg.get("from", {}).get("id")
            if not is_allowed(user_id, self.allowlist):
                return []  # silently dropped, per Part 5.1 — no error, no reply
            return [InboundMessage(
                user_id=str(user_id), chat_id=str(msg["chat"]["id"]),
                text=msg.get("text", ""), raw=update,
            )]

        if "callback_query" in update:
            cq = update["callback_query"]
            user_id = cq.get("from", {}).get("id")
            if not is_allowed(user_id, self.allowlist):
                return []
            request_id, decision, remember = cq["data"].split(":")
            return [InboundCallback(
                user_id=str(user_id), chat_id=str(cq["message"]["chat"]["id"]),
                request_id=request_id, decision=decision, remember=bool(int(remember)),
                callback_query_id=cq["id"], raw=update,
            )]

        return []
