# The Ledger

Every ticket must be completable within one usage window. That's a design constraint, not a
hope: the decompose stage (`orchestrator`) enforces it, and any ticket estimated above budget
is split before it is queued. Sizing is in *steps*, not tokens — a step is one tool-call
sequence ending in a durable artifact.

State lives on disk, in `company/ledger.db` (SQLite, gitignored — it's local per-checkout
state), never in a chat session. A session is a cache, not a database: a ticket can resume with
zero session context and lose at most one step, because the resume packet is assembled from the
ledger, not recovered from a conversation.

## State machine

```
                    ┌──────────────────────────────────┐
                    ▼                                  │
draft → queued → claimed → running ──► checkpointed ───┘
                              │              │
                              ▼              ▼
                        blocked_quota    review → done
                              │              │
                         (reset time)        ▼
                              │          rejected → queued
                              ▼
                            queued
running → failed → queued (attempts < 3) | dead (attempts >= 3)
```

| From | To | Trigger |
|---|---|---|
| `draft` | `queued` | Ticket has a brief and a `done_when`; ready to be claimed. |
| `queued` | `claimed` | A runner (human or autonomous) claims it — dependencies must all be `done`. |
| `claimed` | `running` | Execution starts. |
| `running` | `checkpointed` | An atomic step completes and is committed. |
| `checkpointed` | `running` | More steps remain; continue. |
| `checkpointed` | `review` | The final step completed; hand off to an independent reviewer. |
| `running` | `blocked_quota` | Usage limit hit mid-step. Claim released, `blocked_until` set. |
| `blocked_quota` | `queued` | The usage window resets. |
| `running` | `failed` | The step errored. `attempts` increments. |
| `failed` | `queued` | `attempts < 3` — retry. |
| `failed` | `dead` | `attempts >= 3` — stop retrying; needs a human. |
| `review` | `done` | An independent reviewer approves. |
| `review` | `rejected` | An independent reviewer sends it back, with a reason. |
| `rejected` | `queued` | Re-enters the queue for another attempt. |

`done` and `dead` are terminal. Any transition not in this table is rejected by
`shell/ledger/ledger.py`'s `TRANSITIONS` table — the state machine is enforced in code, not by
convention.

## Schema

```sql
CREATE TABLE tickets (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL DEFAULT 'default',   -- every table is project-scoped from day one
  parent_id     TEXT,
  stage         TEXT NOT NULL DEFAULT 'intake',     -- pipeline stage: intake..release
  state         TEXT NOT NULL DEFAULT 'draft',
  assignee      TEXT,
  branch        TEXT,
  session_id    TEXT,          -- for --resume
  brief         TEXT NOT NULL,
  done_when     TEXT NOT NULL, -- machine-checkable exit contract
  attempts      INTEGER NOT NULL DEFAULT 0,
  blocked_until TEXT,          -- ISO8601, quota reset
  created_at    TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE checkpoints (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id  TEXT NOT NULL REFERENCES tickets(id),
  project_id TEXT NOT NULL,
  step_no    INTEGER NOT NULL,
  summary    TEXT NOT NULL,   -- what was done
  artifacts  TEXT NOT NULL,   -- JSON: paths, commit SHAs
  next_step  TEXT NOT NULL,   -- what to do on resume
  created_at TEXT NOT NULL
);

CREATE TABLE deps   (ticket_id TEXT, depends_on TEXT, PRIMARY KEY (ticket_id, depends_on));
CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT, project_id TEXT,
                      kind TEXT NOT NULL, payload TEXT, created_at TEXT NOT NULL);
```

`project_id` is on every table starting in Phase 1, not retrofitted later — see the addendum's
revised build order. The full `projects` lifecycle table (proposed → greenlit → active →
shipped → maintained → shelved → archived) is a later phase; for now `project_id` is a plain
string tag with a `'default'` fallback.

## Checkpointing rules

- **Every step is idempotent.** Re-running it produces the same result. A dedicated branch per
  ticket makes this true for code work.
- **Every step ends in a commit.** Work in progress with nothing committed is work lost.
- **Nothing irreversible without approval.** No pushes to main, no deletes, no deploys. Agents
  propose; humans dispose.

## CLI (Phase 1)

```bash
python -m shell.ledger.cli add --brief "..." --done-when "..." [--project P] [--depends-on ID ...]
python -m shell.ledger.cli resume [--project P]
python -m shell.ledger.cli next [--project P] [--assignee NAME]
python -m shell.ledger.cli checkpoint <id> --summary "..." --artifacts '["a.py"]' --next-step "..." [--final] [--fail] [--blocked-until ISO8601]
python -m shell.ledger.cli status [<id>] [--project P]
```

- `add` creates a ticket in `draft` and immediately queues it (dependencies gate *claiming*,
  not queuing — see `next_ready` in `shell/ledger/ledger.py`).
- `resume` looks for a ticket orphaned in `running` — one whose driving session died mid-step
  without checkpointing — and returns it with its last checkpoint as a resume packet, without
  re-claiming it. `/foundry:next` always checks this before claiming new work; it's the
  Phase 3 gate ("kill a run mid-ticket; it resumes losing one step").
- `next` finds the oldest `queued` ticket whose dependencies are all `done`, claims it, starts
  it running, and prints a resume packet (brief, `done_when`, last checkpoint, next step).
- `checkpoint` records a checkpoint and either loops back to `running` (more work to do,
  default) or advances to `review` (`--final`); `--fail` and `--blocked-until` instead route
  through the failure/quota branches without recording a checkpoint.
- `status` prints either one ticket's full history (ticket + checkpoints + events) or the whole
  board's per-state counts and ticket list.

The full `Ledger` class (`shell/ledger/ledger.py`) also exposes `queue`, `claim`,
`start_running`, `resume_running`, `advance_to_review`, `block_quota`,
`release_expired_blocks`, `fail`, `approve`, `reject`, and `requeue` directly, for use by
scheduler code and tests. `tests/test_ledger.py` walks a ticket through every state in the
table above.

## Checkpoint enforcement (Phase 3)

`plugin/hooks/hooks.json` registers `plugin/hooks/checkpoint_gate.py` as a `PostToolUse` hook
matched on `Edit|Write|Bash`. It can't stop a commit from happening (PostToolUse fires after
the tool already ran), but the moment a `git commit` runs without a matching
`shell.ledger.cli ... checkpoint` call, every subsequent tool call is blocked (exit code 2,
stderr explains why) until one is made. See `tests/test_hooks.py` and docs/USAGE.md's sibling
hook (`session_log.py`) for the session-boundary side of the same file.

## What's next (see the addendum's revised build order)

- **Phase 1**: ledger schema, state machine, CLI — done.
- **Phase 2**: plugin agents wired to `/foundry:next` (`plugin/commands/next.md`) — done. Not
  yet exercised end-to-end against a real ticket ("brief → PR in attended mode" as the gate
  requires) — that needs an actual session driving it, not just the wiring.
- **Phase 3**: checkpoint hook + resume packet — done (`checkpoint_gate.py`, `Ledger.resumable`,
  `session_log.py`). Same caveat: needs a real kill-mid-ticket run to fully exercise the gate,
  not just unit tests simulating one.
- **Phase 4**: `projects` table and lifecycle state machine — done. See `docs/PORTFOLIO.md`.
- **Phase 5**: autonomous runner + fair-share portfolio scheduler — done, with two honest
  gaps: nothing runs `scheduler_tick` on a timer yet, and the pre-emptive 85%-of-window pause
  has no real consumption signal to read. See `docs/AUTONOMOUS.md`.
- **Phase 6**: Mission Control (reads the ledger and filesystem; no new backend).
- **Phase 7+**: messaging bridge, `librarian` knowledge pipeline, cross-project promotion.
