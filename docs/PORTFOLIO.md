# Portfolio: project lifecycle

`shell/ledger/projects.py` (`Portfolio`), addendum Part 11. A project is metadata layered on
top of the ticket ledger, sharing the same SQLite file. `tickets.project_id` has no foreign
key into `projects.id` on purpose: Phase 1 tickets work with a bare `project_id` string and no
`projects` row at all — creating a `projects` entry is opt-in enrichment (priority, WIP limit,
lifecycle, releases), not a requirement for a ticket to exist.

## State machine

```
proposed ──► greenlit ──► active ──► shipped ──► maintained
    │            │           │                        │
    ▼            ▼           ▼                        ▼
rejected      shelved ◄──────┴────────────────────────┘
                 │  ▲
                 ▼  │
             archived  revived ──► active
```

| State | Meaning |
|---|---|
| `proposed` | An idea with a brief. Costs nothing. |
| `greenlit` | Approved for work. Budget and WIP slot allocated. |
| `active` | Under development. |
| `shipped` | Released. First version out. |
| `maintained` | Live, receiving fixes only. |
| `shelved` | Stopped deliberately. Context preserved, not deleted. |
| `revived` | Coming back — requires a revival brief before returning to `active`. |
| `archived` | Terminal. Read-only. Knowledge retained. |
| `rejected` | Never started. Reason recorded. |

Transitions not in this table raise `ValueError`, same discipline as the ticket ledger's
`TRANSITIONS`. Every transition requires a non-empty `rationale` — this is stricter than the
addendum's literal text (which mandates a reason only for shelving) but consistent with its
spirit: an append-only decision log is only useful if nothing gets in without a reason.

## Shelving is enforced, not just documented (Part 11.3)

`Portfolio.shelve()` requires both `reason` and `revive_when` to be non-empty, raising
`ValueError` otherwise — the two of the addendum's three shelving requirements that are
mechanically checkable. The third (a `docs` agent retro in `knowledge/retros/`) is a workflow
step for the pipeline to enforce once it exists, not something a database constraint can
verify.

## CLI

```bash
python -m shell.ledger.cli project add --id p-1 --name "Widget" --brief "..." [--priority 5] [--wip-limit 3]
python -m shell.ledger.cli project greenlight p-1 --rationale "..."
python -m shell.ledger.cli project start p-1 --rationale "..."
python -m shell.ledger.cli project ship p-1 --rationale "..." [--version 0.1.0 --tag v0.1.0]
python -m shell.ledger.cli project maintain p-1 --rationale "..."
python -m shell.ledger.cli project shelve p-1 --reason "..." --revive-when "..."
python -m shell.ledger.cli project revive p-1 --rationale "..."
python -m shell.ledger.cli project archive p-1 --rationale "..."
python -m shell.ledger.cli project reject p-1 --rationale "..."
python -m shell.ledger.cli project list [--state STATE]
python -m shell.ledger.cli project shelf                 # every shelved project
python -m shell.ledger.cli project status p-1             # project + events + releases
```

## What's not built yet

The addendum's Part 12 (fair-share scheduling, WIP limits, portfolio modes) reads
`Portfolio.list_projects()` and each project's `priority`/`wip_limit`/`budget_share` to decide
which project's ticket runs next — that scheduler is Phase 5, not this phase. This phase only
gets the projects themselves onto disk with an enforced lifecycle.
