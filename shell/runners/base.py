"""The runner interface every provider backend implements.

Compliance rule 8 (COMPLIANCE.md): Anthropic is one runner among several. Nothing in the
scheduler or ledger knows which backend is executing a ticket — it only knows `Runner`.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RunResult:
    ok: bool
    quota_exhausted: bool = False
    reset_at: Optional[str] = None  # ISO8601, when known
    error: Optional[str] = None
    raw_message: Optional[str] = None  # the exact provider text, logged on every quota event
    session_id: Optional[str] = None


@dataclass
class ResumePacket:
    """Everything a runner needs to pick a ticket up with zero session context."""

    ticket_id: str
    brief: str
    done_when: str
    last_checkpoint_summary: Optional[str] = None
    next_step: Optional[str] = None
    artifacts: list = field(default_factory=list)
    session_id: Optional[str] = None


class Runner:
    """Base class. A runner never spawns a model call in attended mode (Part 1.3) — only
    concrete autonomous backends (anthropic_api, bedrock, vertex, openai, local) do that, and
    each must refuse to start without an explicit credential (compliance rule 2)."""

    name = "base"

    def headroom(self) -> bool:
        """True if this runner believes it has quota to start new work. Pre-emptive guard
        (Part 3.4): a scheduler should stop claiming new tickets before hitting a hard limit,
        not react to one."""
        raise NotImplementedError

    def busy(self) -> bool:
        """True if this runner is already executing something. Concurrency defaults to 1
        (compliance rule 4) — raising it is an explicit, documented, per-user choice."""
        raise NotImplementedError

    def run(self, packet: ResumePacket) -> RunResult:
        raise NotImplementedError
