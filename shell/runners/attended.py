"""The attended runner: a documentation object, not an executor.

In attended mode (Part 1.3), the shell never spawns a model call. It prepares a work packet
and stops — the human runs `/foundry:next` in official Claude Code, and that session (using
the subscription, natively) does the work. `AttendedRunner.run()` exists only so a scheduler
loop written against the `Runner` interface fails loudly and legibly if something tries to
call it, instead of silently doing nothing.
"""

from .base import Runner, RunResult


class AttendedRunner(Runner):
    name = "attended"

    def headroom(self) -> bool:
        return True  # not this runner's concern; Claude Code's own limits apply

    def busy(self) -> bool:
        return False  # attended mode has no concept of "the runner is busy"

    def run(self, packet):
        raise RuntimeError(
            "AttendedRunner.run() should never be called. Attended mode means a human runs "
            "/foundry:next inside official Claude Code; nothing in shell/ spawns a model call "
            "for it (see COMPLIANCE.md and blueprint Part 1.3)."
        )
