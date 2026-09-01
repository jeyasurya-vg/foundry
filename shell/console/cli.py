"""CLI entry point for Mission Control.

    python -m shell.console.cli [--repo-root .] [--host 127.0.0.1] [--port 8787]
"""

import argparse

from .server import make_server


def build_parser():
    parser = argparse.ArgumentParser(prog="foundry-console")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--ledger-db")
    parser.add_argument("--usage-db")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--allow-non-loopback", action="store_true",
        help="override the loopback-only default (Part 5.2) - see docs/CONSOLE.md before using this",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    server = make_server(
        repo_root=args.repo_root, ledger_db=args.ledger_db, usage_db=args.usage_db,
        host=args.host, port=args.port, allow_non_loopback=args.allow_non_loopback,
    )
    print(f"Mission Control: http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
