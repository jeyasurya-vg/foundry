"""The bridge interface every provider (Telegram, Slack, Matrix, Discord) implements.

Part 5.1: "The bridge never reasons. It routes, queues and renders. All intelligence is in
the agents." Nothing in here decides anything — it sends text, sends an approval prompt with
three buttons, and reports back what came in.
"""

from dataclasses import dataclass, field


@dataclass
class InboundMessage:
    user_id: str
    chat_id: str
    text: str
    raw: dict = field(default_factory=dict)


@dataclass
class InboundCallback:
    """A button press on an approval message."""

    user_id: str
    chat_id: str
    request_id: str
    decision: str  # "approved" | "denied"
    remember: bool
    callback_query_id: str
    raw: dict = field(default_factory=dict)


class Bridge:
    name = "base"

    def send(self, chat_id, text):
        raise NotImplementedError

    def send_approval_request(self, chat_id, text, request_id):
        raise NotImplementedError

    def poll(self, timeout=25):
        """One long-poll cycle. Returns InboundMessage/InboundCallback events, already
        filtered to the configured allowlist — Part 5.1: 'everything else silently
        dropped.'"""
        raise NotImplementedError
