# Foundry

An open-source framework for running a software company staffed entirely by AI agents:
product, architecture, engineering, QA, security, docs, release and ops. Agents pick up
tickets, do the work, review each other, and ship. A human sits at the board level.

Status: Phases 0-4 built — repo structure, compliance and charter docs, the ledger (schema,
state machine, CLI), `/foundry:next` wired to the plugin's agents with a checkpoint-enforcing
hook, the portfolio (`projects` table and lifecycle), and a cross-provider usage tracker. See
`docs/LEDGER.md` for the build order and what's still ahead (Phase 5+).

## Layout

```
plugin/     PLANE 1 — the company. Pure Claude Code artifacts (agents, commands, hooks).
            Independently useful: install this alone and run official Claude Code.
            commands/next.md is `/foundry:next`; hooks/hooks.json wires session logging and
            checkpoint enforcement.
company/    Scaffolded company memory: charter, org chart, curated memory, knowledge base.
shell/      PLANE 2 (optional) — provider-agnostic ops shell.
            ledger/    ticket state machine + CLI, and the portfolio (project lifecycle).
            usage/     cross-provider quota tracker (Claude/Codex/Ollama) — see docs/USAGE.md.
            scheduler/ bridge/ console/ runners/  not yet built (Phase 5+).
            Never touches OAuth credentials; API-key-first.
docs/       LEDGER.md, PORTFOLIO.md, USAGE.md.
tests/      pytest suite for the ledger, portfolio, usage tracker, and plugin hooks.
```

Read `COMPLIANCE.md` first — it explains why the repo is split into two planes and what rules
are non-negotiable. Then `company/CHARTER.md` and `company/ORG.md` for how the company itself
operates.

## The ledger (Phase 1)

```
pip install pytest          # only dev dependency
pytest -q                   # runs the full state-machine test suite

python -m shell.ledger.cli add --brief "..." --done-when "..."
python -m shell.ledger.cli next
python -m shell.ledger.cli checkpoint <ticket-id> --summary "..." --next-step "..." --final
python -m shell.ledger.cli status
```

Ledger state defaults to `company/ledger.db` (gitignored — it's local, per-checkout state).
Full schema and state diagram: `docs/LEDGER.md`. Project/portfolio commands live under
`python -m shell.ledger.cli project ...` — see `docs/PORTFOLIO.md`.

## Usage tracker

```
python -m shell.usage.cli record --provider claude --window session --remaining 0.58 --reset 2026-09-01T17:00:00Z
python -m shell.usage.cli status
```

Tracks Claude/Codex/Ollama session and weekly quota as a self-logged ledger, not a live
poller — see `docs/USAGE.md` for why (short version: the only live numbers require reusing a
subscription OAuth session token outside its client, which `COMPLIANCE.md` forbids).

## Attended vs. autonomous

- **Attended** (default): you run official Claude Code; the ledger tracks tickets on disk.
  No model calls originate from `shell/`.
- **Autonomous** (`shell/`, not yet built — see `docs/LEDGER.md` build order): requires an
  explicit API key. Refuses to start without one.
