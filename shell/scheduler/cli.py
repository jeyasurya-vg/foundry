"""CLI / daemon loop for the Foundry scheduler (the autonomous runner's tick loop).

    python -m shell.scheduler.cli --runner anthropic-api --mode balanced --interval 60

Runs forever, calling `scheduler_tick` every `--interval` seconds, until Ctrl+C / SIGTERM.
Only `anthropic-api` is a real dispatching runner today (compliance rule 2: requires
`ANTHROPIC_API_KEY`, no fallback); every other registry entry is a stub, or `attended`
(attended's `run()` fails loudly on purpose if a ticket ever actually reaches it - see
shell/runners/attended.py). `--runner` is required; there is no default, matching the "no
auto-detection" rule the runner itself enforces. See docs/AUTONOMOUS.md.
"""

import argparse
import os
import signal

from ..ledger.ledger import DEFAULT_DB_PATH, Ledger
from ..ledger.projects import Portfolio
from ..runners import RUNNERS
from .daemon import run_forever
from .fairshare import MODES


def build_parser():
    parser = argparse.ArgumentParser(prog="foundry-scheduler")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="path to the ledger/portfolio sqlite file")
    parser.add_argument("--mode", choices=MODES, default="balanced")
    parser.add_argument("--runner", required=True, choices=sorted(RUNNERS.keys()))
    parser.add_argument("--interval", type=float, default=60, help="seconds between ticks")
    parser.add_argument("--max-ticks", type=int, default=None, help="stop after N ticks (testing/manual runs)")
    parser.add_argument("--pidfile", help="write the process id here while running; removed on clean exit")
    return parser


def _write_pidfile(path):
    if path:
        with open(path, "w") as f:
            f.write(str(os.getpid()))


def _remove_pidfile(path):
    if path and os.path.exists(path):
        os.remove(path)


def main(argv=None):
    args = build_parser().parse_args(argv)

    ledger = Ledger(args.db)
    portfolio = Portfolio(args.db)
    runner = RUNNERS[args.runner]()

    stop = {"flag": False}

    def _handle_signal(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    _write_pidfile(args.pidfile)
    print(
        f"Foundry scheduler: runner={args.runner} mode={args.mode} interval={args.interval}s "
        "(Ctrl+C to stop)"
    )
    try:
        ticks = run_forever(
            ledger, portfolio, runner,
            mode=args.mode, interval=args.interval, max_ticks=args.max_ticks,
            should_stop=lambda: stop["flag"],
        )
        print(f"Scheduler stopped after {ticks} tick(s).")
    finally:
        _remove_pidfile(args.pidfile)
        ledger.close()
        portfolio.close()


if __name__ == "__main__":
    main()
