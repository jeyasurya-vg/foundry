"""Mission Control: a local web console. No new backend — every request opens a short-lived
connection to the same ledger/portfolio/usage SQLite files everything else uses, and reads a
couple of files off disk. Stdlib only (`http.server`): this project stays dependency-light on
purpose, and a local dashboard is exactly the kind of thing the standard library already does.

Part 5.2: "Serve on loopback. Remote access via a private mesh network, never a public port."
`make_server` enforces that by default — binding to anything else requires an explicit,
unmissable opt-in, the same "no fallback" discipline as the compliance rules elsewhere.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import api
from ..ledger.ledger import DEFAULT_DB_PATH as LEDGER_DEFAULT_DB, Ledger
from ..ledger.projects import Portfolio
from ..usage.db import DEFAULT_DB_PATH as USAGE_DEFAULT_DB
from ..usage.tracker import UsageTracker

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, content_type: str, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status=200):
        self._send(json.dumps(payload, indent=2, default=str).encode("utf-8"), "application/json", status)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        project_id = query.get("project", [None])[0]
        ticket_id = query.get("ticket", [None])[0]

        ledger = Ledger(self.server.ledger_db)
        portfolio = Portfolio(self.server.ledger_db)
        usage = UsageTracker(self.server.usage_db)
        try:
            if parsed.path == "/":
                self._send(TEMPLATE_PATH.read_bytes(), "text/html; charset=utf-8")
            elif parsed.path == "/api/dashboard":
                self._json(api.build_dashboard(ledger, portfolio, usage))
            elif parsed.path == "/api/board":
                self._json(api.build_board(ledger, project_id=project_id))
            elif parsed.path == "/api/portfolio":
                self._json(api.build_portfolio(portfolio))
            elif parsed.path == "/api/team":
                self._json(api.build_team(self.server.repo_root))
            elif parsed.path == "/api/memory":
                self._json(api.build_memory(self.server.repo_root))
            elif parsed.path == "/api/skills":
                self._json(api.build_skills(self.server.repo_root))
            elif parsed.path == "/api/runs":
                self._json(api.build_runs(ledger, project_id=project_id))
            elif parsed.path == "/api/runs/detail":
                if not ticket_id:
                    self._json({"error": "missing ?ticket="}, status=400)
                else:
                    self._json(api.build_run_detail(ledger, ticket_id))
            else:
                self._json({"error": "not found"}, status=404)
        finally:
            ledger.close()
            portfolio.close()
            usage.close()

    def log_message(self, format, *args):
        pass  # a loopback-only local tool doesn't need an access log by default


def make_server(repo_root=".", ledger_db=None, usage_db=None, host="127.0.0.1", port=8787,
                 allow_non_loopback=False):
    if host not in LOOPBACK_HOSTS and not allow_non_loopback:
        raise ValueError(
            f"refusing to bind Mission Control to {host!r}: Part 5.2 requires loopback-only "
            "by default ('never a public port'). Pass allow_non_loopback=True if you have "
            "your own reason to override this — e.g. serving through a private mesh network "
            "you already trust, per the same section."
        )
    repo_root = Path(repo_root)
    server = ThreadingHTTPServer((host, port), Handler)
    server.repo_root = repo_root
    server.ledger_db = Path(ledger_db) if ledger_db else repo_root / LEDGER_DEFAULT_DB
    server.usage_db = Path(usage_db) if usage_db else repo_root / USAGE_DEFAULT_DB
    return server
