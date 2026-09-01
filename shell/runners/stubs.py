"""Stub runners: same `Runner` interface, not implemented yet.

Compliance rule 8 (COMPLIANCE.md): provider-agnostic by construction. These exist so the
architecture is visibly not Anthropic-only, without pretending they're built. Each refuses to
start with a clear message rather than silently doing nothing — same discipline as the
`codex`/`ollama_cloud` stubs in `shell/usage/providers.py`.
"""

from .base import Runner, RunResult


class _StubRunner(Runner):
    def headroom(self):
        return False

    def busy(self):
        return False

    def run(self, packet):
        return RunResult(ok=False, error=f"runner '{self.name}' is not implemented yet")


class BedrockRunner(_StubRunner):
    name = "bedrock"


class VertexRunner(_StubRunner):
    name = "vertex"


class OpenAIRunner(_StubRunner):
    name = "openai"


class LocalRunner(_StubRunner):
    name = "local"
