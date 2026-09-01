"""Capped exponential backoff with jitter, persisted so a restart doesn't reset it.

Part 3.5: "Vendors notice retry-storms far more than they notice volume, and a well-behaved
client is the cheapest insurance this project can buy."
"""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_BASE_SECONDS = 5
DEFAULT_CAP_SECONDS = 3600  # 1 hour hard ceiling
DEFAULT_STATE_PATH = "company/.backoff_state.json"


def delay_seconds(attempt, base=DEFAULT_BASE_SECONDS, cap=DEFAULT_CAP_SECONDS, rng=random):
    """attempt is 1-indexed. Full jitter: uniform(0, min(cap, base * 2**(attempt-1)))."""
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    ceiling = min(cap, base * (2 ** (attempt - 1)))
    return rng.uniform(0, ceiling)


class Backoff:
    """Tracks consecutive-failure count and the next allowed retry time on disk, keyed by a
    name (e.g. a runner or provider id) so unrelated backoffs don't share state."""

    def __init__(self, key, state_path=DEFAULT_STATE_PATH, base=DEFAULT_BASE_SECONDS, cap=DEFAULT_CAP_SECONDS):
        self.key = key
        self.state_path = Path(state_path)
        self.base = base
        self.cap = cap

    def _load(self):
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, state):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state))

    def ready(self, now=None):
        now = now or datetime.now(timezone.utc)
        state = self._load().get(self.key)
        if not state:
            return True
        next_allowed = datetime.fromisoformat(state["next_allowed_at"])
        return now >= next_allowed

    def record_failure(self, now=None, rng=random):
        now = now or datetime.now(timezone.utc)
        all_state = self._load()
        entry = all_state.get(self.key, {"attempt": 0})
        entry["attempt"] += 1
        wait = delay_seconds(entry["attempt"], base=self.base, cap=self.cap, rng=rng)
        entry["next_allowed_at"] = (now + timedelta(seconds=wait)).isoformat()
        all_state[self.key] = entry
        self._save(all_state)
        return wait

    def reset(self):
        all_state = self._load()
        all_state.pop(self.key, None)
        self._save(all_state)
