# Contributing

Read `COMPLIANCE.md` first. It's short, and it's the one document every change has to stay
compatible with — CI enforces rule 1 mechanically (a grep for OAuth/credential-store access
in `shell/` and `plugin/` source), and the rest is judgment CI can't check for you.

## Setup

```bash
pip install pytest        # the only dev dependency, on purpose — see "dependencies" below
pytest -q                 # full suite
```

No build step. No compiled assets. `shell/` is plain Python (3.9+), `plugin/` is markdown and
JSON.

## Where things live

- `plugin/` — Plane 1, pure Claude Code artifacts (agents, commands, hooks). Changes here
  should keep working with *only* the plugin installed, no `shell/` present — see the note at
  the bottom of `plugin/commands/next.md` for the one place this repo currently leans on
  `shell/` being there anyway (both live in the same repo today).
- `shell/ledger/` — the ticket state machine (`ledger.py`) and portfolio lifecycle
  (`projects.py`). Both follow the same shape: a `TRANSITIONS`-style dict, a private
  `_transition()` that validates against it and logs an event, and small public methods named
  after what they do (`claim`, `checkpoint`, `shelve`, never a generic `transition(state)`).
- `shell/usage/`, `shell/runners/`, `shell/scheduler/`, `shell/console/` — each has a
  corresponding `docs/*.md` file. Update the doc in the same change as the code; a stale doc
  is worse than no doc, because it's trusted.

## Adding things

**A new department agent** — per `company/ORG.md`'s dynamic-hiring rule, this isn't a
unilateral addition even for a human contributor: propose it (a PR adding the agent file and
an `ORG.md` entry, with a description of what work it owns and why no existing department
covers it) rather than merging it straight in. The `tools:` frontmatter can't fence `Bash` to
specific commands for a plugin-shipped agent (see the note at the top of `company/ORG.md`) —
state the restriction as a rule in the agent's own body instead, the way `engineer.md` does.

**A new runner backend** (Bedrock, Vertex, a real one to replace a stub in
`shell/runners/stubs.py`) — implement the `Runner` interface (`headroom()`, `busy()`,
`run(packet) -> RunResult`) from `shell/runners/base.py`. It must refuse to start without an
explicit credential for that provider (compliance rule 2) — no fallback, no auto-detection,
same discipline as `AnthropicAPIRunner`. Route quota detection through
`shell/runners/quota.classify()` rather than reinventing pattern matching.

**A new usage-tracker provider** — add an entry to `shell/usage/providers.py`'s `PROVIDERS`
dict. Start it as `"status": "stub"` unless you have a real, ToS-compliant way to source live
numbers for it — see `docs/USAGE.md`'s "why self-logged, not polled" section before wiring up
anything that reads a subscription OAuth session token from disk. That line does not move for
any provider, not just Claude.

## Dependencies

The only runtime dependency across the whole repo is the Python standard library; `pytest` is
dev-only. Keep it that way unless there's a genuinely good reason — `shell/console` is a real
web server built on `http.server` specifically to avoid pulling in Flask/FastAPI for a
loopback-only local tool, and `shell/runners/quota.py` uses JSON pattern files instead of
YAML to avoid a PyYAML dependency. If a change needs a new dependency, say why the standard
library isn't enough in the PR description.

## Tests

Every module with behavior has a `tests/test_*.py` file exercising it — state machines are
tested by walking every transition (see `test_ledger.py`, `test_projects.py`), CLIs are
tested via `subprocess` smoke tests, hooks are tested by piping JSON into the script over
stdin exactly as Claude Code would. Match the existing pattern in the file you're touching
rather than introducing a new testing style.

## Third-party code

Nothing in this repo currently vendors or depends on unreviewed third-party skills or
converters. If you're adding one (the addendum's `librarian`/`book-to-skill` integration is
the known future case), it needs a source URL, a pinned commit, and a recorded permission
surface before it's wired into anything an agent can load — see Part 6 of the blueprint
(`foundry-blueprint.md`, kept at the repo's origin for reference) and `docs/ROADMAP.md`'s
entry on why this hasn't been started yet.

## Commit and PR expectations

- Run `pytest -q` before opening a PR; CI runs it again, but don't rely on CI to find what a
  local run would have caught in ten seconds.
- One logical change per PR. This repo's own history (look at the commit log) is the pattern
  to follow: each commit is one phase or one coherent piece of a phase, with the test count
  and what was and wasn't verified live stated plainly in the message.
- If a change touches `plugin/agents/*.md` tool fences, re-read the note at the top of
  `company/ORG.md` first — it's a common mistake to write a fenced `Bash(...)` pattern that
  silently does nothing there.
