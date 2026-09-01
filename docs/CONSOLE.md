# Mission Control

Phase 6. A local web console — Part 5.2: "no new backend: it reads the ledger and the
filesystem." `shell/console` opens the same SQLite files every other tool uses and reads a
couple of markdown files; it writes nothing.

## Running it

```bash
python -m shell.console.cli                      # http://127.0.0.1:8787
python -m shell.console.cli --port 8080
python -m shell.console.cli --repo-root /path/to/foundry
```

Or via the installed entry point: `foundry-console`.

## Screens built

| Screen | Reads |
|---|---|
| Dashboard | `Ledger.status_summary()`, project counts by state, `UsageTracker.status()`, `Ledger.recent_events()` (the live event feed) |
| Board | `Ledger.list_tickets()`, kanban columns by state |
| Portfolio | `Portfolio.list_projects()` (lifecycle board) + `Portfolio.shelf()` |
| Team | `plugin/agents/*.md` frontmatter — name, description, tool fence |
| Memory | `company/MEMORY.md` and `company/knowledge/INDEX.md`, read whole |

## Screens from the blueprint not built here

- **Calendar** (scheduled jobs) — there's no scheduled-job system yet; `shell/scheduler`
  builds `scheduler_tick()` as a function you call, not a daemon with a job history (see
  `docs/AUTONOMOUS.md`'s "what's not built yet"). Nothing to show.
- **Skills** (inventory, permission surface, integrity checks) — Phase 8; there's no skill
  loader yet.
- **Settings** (fences, concurrency, budgets, provider config, backoff params) — most of these
  values live in code defaults today (`shell/runners/backoff.py`'s constants, `Runner`
  concurrency), not a config file a screen could read and let you edit safely.
- **Runs** (per-ticket timeline: steps, checkpoints, quota pauses, resumes) — mostly covered
  by Dashboard's event feed and Board today; a dedicated per-ticket timeline view combining
  `list_checkpoints()` + `list_events()` (both already exist on `Ledger`) is a small addition
  whenever it's wanted, not a new subsystem.

Building a screen with no real data behind it would mean fabricating something to display —
worse than not having the tab.

## Loopback only, by design

`make_server()` refuses to bind anywhere except `127.0.0.1`/`localhost`/`::1` unless you pass
`allow_non_loopback=True` explicitly. Part 5.2: "Serve on loopback. Remote access via a
private mesh network, never a public port." If you need remote access, put a private mesh
network (e.g. Tailscale) in front of it — don't flip this flag to expose it directly.

## API

Every screen is backed by a small JSON endpoint, all in `shell/console/api.py` as plain
functions (testable without a server) and wired to HTTP in `shell/console/server.py`:

- `GET /api/dashboard`
- `GET /api/board[?project=<id>]`
- `GET /api/portfolio`
- `GET /api/team`
- `GET /api/memory`

No authentication — this is a loopback-only local tool, the same trust boundary as running
`python` directly on your own machine.
