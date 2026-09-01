# Roadmap: what's built, what isn't, and why

One canonical status page, instead of a "what's next" footnote scattered across five docs.
Each phase links to the doc with the real detail.

## Built (Phases 0-6, 9)

| Phase | What | Doc |
|---|---|---|
| 0 | Repo, licence, `COMPLIANCE.md`, CI credential-access grep | `COMPLIANCE.md` |
| 1 | Ledger schema, ticket state machine, CLI (`add`/`next`/`checkpoint`/`status`) | `docs/LEDGER.md` |
| 2 | `/foundry:next`, plugin hooks wiring, agent dispatch by pipeline stage | `docs/LEDGER.md` |
| 3 | Checkpoint-enforcing `PostToolUse` hook, orphan-ticket resume (`Ledger.resumable`) | `docs/LEDGER.md` |
| 4 | `projects` table, portfolio lifecycle state machine, mandatory shelve reason | `docs/PORTFOLIO.md` |
| 5 | Autonomous runner (API-key-gated), quota detection, backoff, fair-share scheduler | `docs/AUTONOMOUS.md` |
| 6 | Mission Control (Dashboard/Board/Portfolio/Team/Memory) | `docs/CONSOLE.md` |
| — | Cross-provider usage tracker (Claude active, Codex/Ollama stubbed) | `docs/USAGE.md` |
| 9 | Docs, examples, contribution guide (this pass) | `CONTRIBUTING.md`, `examples/` |

86 tests as of this writing, all passing, run via `pytest -q` — including one
(`test_quickstart.py`) that runs `examples/quickstart.py` end to end on every invocation, so
the "stranger ships something in under an hour" gate stays actually true rather than aspirational.

## Not built, and why

**Phase 7 — Messaging bridge (Telegram/Slack/Matrix/Discord).** Needs a provider decision and
a real bot token/app credential — neither is something to guess at or fake. Not started.

**Phase 7-8 — `librarian` / knowledge pipeline (addendum Part 10).** The blueprint wraps a
specific third-party repo (`virgiliojr94/book-to-skill`) as the converter. Pulling in
unreviewed third-party code is a supply-chain decision this project's own security posture
(Part 6: "treat a skill as code you are about to run, because it is") says shouldn't happen
silently. Needs an explicit go-ahead, or direction to build a smaller native ingestion path
instead. Not started.

**Phase 8 — Injection-test CI gate.** "Ship a fixture containing an embedded instruction and
assert the agent ignores it" requires an actual live model call to verify — the same
API-key boundary the autonomous runner hit in Phase 5. Nothing to test it against yet
(`librarian`, the component most exposed to untrusted input, doesn't exist). Not started.

**Phase 8 — Skill inventory.** No skill loader exists yet (`plugin/skills/` is still an empty
scaffold directory) — nothing to inventory. Not started.

**Phase 8 — Container profile for autonomous mode.** `AnthropicAPIRunner` shells out to the
official `claude` CLI directly on the host; a documented container profile with no host mounts
(Part 6) is real remaining work, distinct from the runner code itself. Not started.

**Addendum Phase 9 — Cross-project promotion flow.** Promoting a retro/ADR from one project's
knowledge into `knowledge/standards/` (Part 12.6) needs `company/knowledge/` to actually have
content in it first — right now it's an empty scaffold (`INDEX.md` says so explicitly). Not
started; revisit once a project has run through its pipeline for real and produced a retro.

**Mission Control screens: Calendar, Skills, Settings, a dedicated Runs timeline.** See
`docs/CONSOLE.md`'s own "screens not built" section — each is blocked on one of the items
above (a scheduled-job system, the skill loader, a real config file, or just not yet prioritized).

**Two items flagged inside Phase 5/6 themselves, not deferred to a later phase:**
- Nothing runs `scheduler_tick()` on a timer — it's a function you call, not a daemon.
- The pre-emptive 85%-of-window pause (Part 3.4) has no real per-runner consumption signal to
  read yet; the usage tracker is self-logged and account-wide, not fed automatically to a
  runner mid-run.

## The honest summary

Everything gated on "you need an external account, a real credential, or a decision only a
human can make" stopped at that gate rather than being faked. Everything else that a phase
asked for is built and tested. If you pick a messaging provider, or want to build a native
(non-third-party) ingestion path for the knowledge pipeline, either is a reasonable next slice
— just not something to start without you weighing in first.
