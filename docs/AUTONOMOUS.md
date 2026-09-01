# Autonomous mode: runner, scheduler, backoff

Phase 5. This is Plane 2, entirely optional, and off by default — attended mode
(`/foundry:next` in official Claude Code) needs none of this.

## The compliance line this phase has to hold

Rule 2 (`COMPLIANCE.md`): autonomous mode requires an explicit API key. No fallback, no
auto-detection. `shell/runners/anthropic_api.py`'s `headroom()` and `run()` both check
`os.environ["ANTHROPIC_API_KEY"]` directly and refuse cleanly if it's absent — there is no
code path anywhere in `shell/` that reads `~/.claude/` or any other credential store (rule 1).
`tests/test_runners.py::test_anthropic_runner_refuses_without_api_key` pins this down.

## Runner interface (`shell/runners/`)

`Runner.headroom()` / `.busy()` / `.run(packet)`, where `packet` is a `ResumePacket` (ticket
id, brief, done_when, last checkpoint summary, next step, artifacts, session id) — the same
information `/foundry:next` hands a department agent in attended mode.

- **`AttendedRunner`** — a documentation object. `.run()` raises; attended mode never spawns a
  model call from `shell/` (Part 1.3).
- **`AnthropicAPIRunner`** — the one real backend. Shells out to the *official* `claude` CLI in
  headless mode (`claude -p ... --append-system-prompt ...`), authenticated by
  `ANTHROPIC_API_KEY` in its own environment. It does not reimplement the Messages API —
  exactly one code path ever talks to Anthropic, and it's Anthropic's own client. Headless
  mode skips auto-discovery of `CLAUDE.md`/hooks/skills (Part 4), so `_build_context()`
  injects `plugin/CLAUDE.md` and `company/ORG.md` explicitly via `--append-system-prompt`.
- **`BedrockRunner` / `VertexRunner` / `OpenAIRunner` / `LocalRunner`** — stubs. Same interface,
  `headroom()` always `False`, `run()` returns a clear "not implemented" `RunResult`. They
  exist so the provider-agnostic architecture (compliance rule 8) is visible in code, not just
  asserted in prose — same pattern as `shell/usage/providers.py`'s Codex/Ollama stubs.

## Quota detection (`shell/runners/quota.py`)

Detection order, per Part 3.4: provider metadata (a dict with a `status` field, when the
caller has one) → a documented exit code (a hook for later; none is documented for the
`claude` CLI today) → a configurable pattern list matched against combined stdout/stderr.
Patterns live in `shell/runners/quota_patterns.json` — plain JSON rather than the blueprint's
suggested YAML, specifically to avoid adding a PyYAML dependency; the "tunable without
touching code" property is identical.

## Backoff (`shell/runners/backoff.py`)

Capped exponential with full jitter (`delay_seconds`), persisted to
`company/.backoff_state.json` (gitignored, like the ledger and usage state) so a process
restart doesn't reset the count — Part 3.5. Keyed by name, so an autonomous runner's backoff
never collides with, say, a future scraper's.

## Fair-share scheduler (`shell/scheduler/`)

`fairshare.score(project, consumed_share)` and `eligible_projects(projects, mode)` are pure
functions on plain dicts (Part 12.2, 12.4) — the four `MODES` are `focus` (highest-priority
active project only), `balanced` (default: every active + maintained project), `maintenance`
(maintained only), `discovery` (proposed + greenlit).

`next_ticket(ledger, portfolio, runner, mode, window_consumed)` wires those to the real
ledger/portfolio: skips a project once `Ledger.wip_count(project_id)` reaches its
`wip_limit`, then picks the highest-scoring project's next ready ticket. `window_consumed`
defaults to "nothing tracked" (pure priority order) — wiring it to real per-project
consumption is future work for whoever builds real spend tracking into `shell/usage`; the
self-logged usage tracker built in Phase 2 tracks account-wide quota, not per-project spend.

`scheduler_tick(ledger, portfolio, runner, ...)` is the Part 3.4 loop: release expired
`blocked_quota` tickets, do nothing if the runner is already busy (concurrency defaults to 1 —
rule 4), otherwise claim and `execute()` the ticket `next_ticket` picked.

`execute()` deliberately does **not** force a successful run's ticket into `checkpointed`
itself. The dispatched agent (running inside the headless `claude -p` call, same as an
attended-mode agent) is expected to call `shell.ledger.cli checkpoint` as part of doing the
work. If it doesn't, the ticket is left `running` — which is exactly the orphan state
`Ledger.resumable()` (Phase 3) already knows how to pick up on the next tick. That composition
is deliberate, not a gap: the failure mode "an agent didn't checkpoint" is the same whether a
human or the autonomous runner was driving.

## What's not built yet

- Nothing actually runs this on a timer. `scheduler_tick` is a function you call, not a daemon
  — wiring a loop around it (a 60s sleep, signal handling, a pidfile) is a small remaining
  piece, deliberately left out until there's a real autonomous deployment to run it against.
- `window_consumed` has no real implementation — see above.
- The pre-emptive pause at ~85% of window (Part 3.4) isn't wired in; it would live in
  `AnthropicAPIRunner.headroom()` once there's a real per-runner consumption signal to check
  against, which doesn't exist yet (the usage tracker is self-logged and account-wide, not
  fed automatically to a runner).
