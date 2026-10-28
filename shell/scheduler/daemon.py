"""A loop around `scheduler_tick` (see docs/AUTONOMOUS.md's former "what's not built yet").

`scheduler_tick` is a function you call once; this is the thin wrapper that calls it
repeatedly on an interval. `sleep` and `should_stop` are injectable so tests can drive the
loop deterministically without ever really blocking.
"""

import time

from .tick import scheduler_tick


def run_forever(
    ledger,
    portfolio,
    runner,
    mode="balanced",
    interval=60,
    max_ticks=None,
    window_consumed=None,
    sleep=time.sleep,
    notify=print,
    should_stop=None,
):
    """Calls `scheduler_tick` every `interval` seconds until `max_ticks` ticks have run or
    `should_stop()` returns true. Returns the number of ticks actually run."""
    ticks = 0
    while True:
        if should_stop is not None and should_stop():
            break
        scheduler_tick(ledger, portfolio, runner, mode=mode, window_consumed=window_consumed, notify=notify)
        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            break
        sleep(interval)
    return ticks
