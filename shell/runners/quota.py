"""Quota-exhaustion detection (Part 3.4): provider metadata, then exit code, then patterns.

A configurable pattern list, not hardcoded strings, because wording changes — the addendum's
own example is Claude Code's usage-limit message drifting across versions. Patterns live in
`shell/runners/quota_patterns.json`, editable without touching code. JSON rather than YAML
specifically to avoid adding a dependency (PyYAML) for a project that already tries hard to
stay dependency-light; the "user-tunable without touching code" property is the same either
way.
"""

import json
import re
from pathlib import Path

DEFAULT_PATTERNS_PATH = Path(__file__).parent / "quota_patterns.json"

DEFAULT_PATTERNS = [
    r"usage limit",
    r"rate limit",
    r"rate.limited",
    r"quota exceeded",
    r"try again later",
    r"resets? at",
]


def load_patterns(path=None):
    path = Path(path) if path else DEFAULT_PATTERNS_PATH
    if not path.exists():
        return list(DEFAULT_PATTERNS)
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list) and all(isinstance(p, str) for p in data):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return list(DEFAULT_PATTERNS)


def classify(exit_code=None, stdout="", stderr="", provider_metadata=None, patterns=None):
    """Returns (quota_exhausted: bool, raw_message: str | None).

    Detection order, per Part 3.4:
    1. Provider rate-limit metadata, when the caller has it (most reliable, checked first).
    2. A specific known exit code, when the provider documents one (none is documented for
       the `claude` CLI today, so this stays a hook for future use, not dead weight).
    3. A configurable pattern list against combined stdout/stderr.
    """
    if provider_metadata:
        status = provider_metadata.get("status")
        if status in ("exceeded", "rate_limited"):
            return True, json.dumps(provider_metadata)

    combined = f"{stdout}\n{stderr}"
    patterns = patterns if patterns is not None else load_patterns()
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            return True, combined.strip()[:2000]  # log the raw message, capped

    return False, None
