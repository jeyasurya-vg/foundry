# Foundry

An open-source framework for running a software company staffed entirely by AI agents:
product, architecture, engineering, QA, security, docs, release and ops. Agents pick up
tickets, do the work, review each other, and ship. A human sits at the board level.

Status: Phase 0/1 scaffold — repo structure, compliance and charter docs, and the ledger
(schema, state machine, CLI) are in place. See `docs/LEDGER.md` for the build order.

## Layout

```
plugin/     PLANE 1 — the company. Pure Claude Code artifacts (agents, skills, commands,
            hooks). Independently useful: install this alone and run official Claude Code.
company/    Scaffolded company memory: charter, org chart, curated memory, knowledge base.
shell/      PLANE 2 (optional) — provider-agnostic ops shell: ledger, scheduler, bridge,
            console, runners. Never touches OAuth credentials; API-key-first.
docs/       LEDGER.md — the ticket state machine and checkpoint contract.
tests/      pytest suite for the ledger.
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
Full schema and state diagram: `docs/LEDGER.md`.

## Attended vs. autonomous

- **Attended** (default): you run official Claude Code; the ledger tracks tickets on disk.
  No model calls originate from `shell/`.
- **Autonomous** (`shell/`, not yet built — see `docs/LEDGER.md` build order): requires an
  explicit API key. Refuses to start without one.
