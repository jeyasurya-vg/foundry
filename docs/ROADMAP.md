# Roadmap: what's built, what isn't, and why

One canonical status page, instead of a "what's next" footnote scattered across five docs.
Each phase links to the doc with the real detail.

## Built (Phases 0-9)

| Phase | What | Doc |
|---|---|---|
| 0 | Repo, licence, `COMPLIANCE.md`, CI credential-access grep | `COMPLIANCE.md` |
| 1 | Ledger schema, ticket state machine, CLI (`add`/`next`/`checkpoint`/`status`) | `docs/LEDGER.md` |
| 2 | `/foundry:next`, plugin hooks wiring, agent dispatch by pipeline stage | `docs/LEDGER.md` |
| 3 | Checkpoint-enforcing `PostToolUse` hook, orphan-ticket resume (`Ledger.resumable`) | `docs/LEDGER.md` |
| 4 | `projects` table, portfolio lifecycle state machine, mandatory shelve reason | `docs/PORTFOLIO.md` |
| 5 | Autonomous runner (API-key-gated), quota detection, backoff, fair-share scheduler, **a daemon loop around `scheduler_tick` (`shell/scheduler/cli.py`)** | `docs/AUTONOMOUS.md` |
| 6 | Mission Control (Dashboard/Board/Portfolio/Team/**Runs**/**Skills**/Memory) | `docs/CONSOLE.md` |
| 7 | Messaging bridge (Telegram) — verified against a real bot and a real button tap; **"approve and remember" appends to an agent's frontmatter fence, channel-per-stream routing, and `request-action` wiring real `Portfolio.ship`/`shelve`/`archive` approval points** | `docs/BRIDGE.md` |
| 8 | Container profile for autonomous mode (`shell/runners/container/`) — no host mounts beyond the project directory itself | `docs/CONTAINER.md` |
| — | Cross-provider usage tracker (Claude active, Codex/Ollama stubbed) | `docs/USAGE.md` |
| 9 | Docs, examples, contribution guide | `CONTRIBUTING.md`, `examples/` |
| — | Skill inventory (2 vendored skills, reviewed): `taste-skill`, `no-ai-slop`, **with an automated `content_sha256` integrity check** | `docs/SKILLS.md` |

167 tests as of this writing, all passing, run via `pytest -q` — including one
(`test_quickstart.py`) that runs `examples/quickstart.py` end to end on every invocation, so
the "stranger ships something in under an hour" gate stays actually true rather than aspirational.

## Not built, and why

**Phase 7 — Slack/Matrix/Discord bridges.** Telegram is built and verified (`docs/BRIDGE.md`)
— the other three would implement the same `Bridge` interface, but each needs its own
provider decision and app credential. Not started.

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

**Addendum Phase 9 — Cross-project promotion flow.** Promoting a retro/ADR from one project's
knowledge into `knowledge/standards/` (Part 12.6) needs `company/knowledge/` to actually have
content in it first — right now it's an empty scaffold (`INDEX.md` says so explicitly). Not
started; revisit once a project has run through its pipeline for real and produced a retro.

**Mission Control screens: Calendar, Settings.** See `docs/CONSOLE.md`'s own "screens not
built" section — Calendar has no scheduled-job history to show even with the scheduler daemon
running (ticks aren't individually tracked jobs); Settings has no config file yet to read and
edit safely (fences/concurrency/budgets/backoff params still live as code constants).

**Inside Phase 7 itself:** calling `request-action` on an irreversible action is still a
manual/explicit step, not something `shell/ledger`/`shell/scheduler` triggers on their own —
see `docs/BRIDGE.md`'s "what's not built yet." And "approve and remember" can only ever be a
human-reviewable note for a plugin-shipped agent, never a platform-enforced fence — that's a
Claude Code platform limit (project-level `.claude/agents/*.md` is where real enforcement
lives), not something this repo can route around.

**One item flagged inside Phase 5 itself, not deferred to a later phase:** the pre-emptive
85%-of-window pause (Part 3.4) has no real per-runner consumption signal to read yet; the
usage tracker is self-logged and account-wide, not fed automatically to a runner mid-run.

## Repos evaluated for inclusion and rejected

A batch of 11 repos plus a skill marketplace (openclawskills.net) was reviewed for possible
inclusion in the same pass that produced `taste-skill` and `no-ai-slop`. Two notes before the
list: fetched "popularity" stats (stars/forks/commits) for all of these were unreliable —
one fetch claimed OpenClaw had "388k stars" and an "OpenClaw Foundation" that didn't appear
in its actual README, so treat any number below (if quoted at all) as unverified. And the
marketplace itself was rejected outright: 5,000+ skills, no formal vetting process — exactly
the unvetted-supply-chain scenario Part 6 exists to guard against. Specific, inspected skills
only, never a marketplace as a source.

| Repo | What it is | Why it's not in Foundry |
|---|---|---|
| `usestrix/strix` | Autonomous AI pentesting/exploit platform | Plausible fit for the `security` department in principle, but "autonomous exploitation" run automatically is a heavy, separate decision — not a drive-by add. |
| `diegosouzapw/OmniRoute` | Multi-provider AI gateway/router | Advertises "TLS stealth" — reads as evading network inspection, which is not a property this compliance-focused project wants near it. |
| `nateherkai/scroll-craft` | Generates scroll-driven marketing sites (needs ffmpeg, Playwright) | Wrong domain — Mission Control is an ops dashboard, not a marketing landing page. |
| `Yuzzyuk/marketing-os` | Markdown skill bundle, full marketing department | Only relevant to marketing Foundry-the-project, not to Foundry's own pipeline. |
| `lfnovo/open-notebook` | Self-hosted NotebookLM alternative | No functional overlap with the ticket/portfolio/agent pipeline. |
| `Bennettxai/FounderOS-DEMO` | A different solo-founder "AI company" demo product | Explicitly a teaching demo with seeded placeholder data, not a library to depend on. |
| `koala73/worldmonitor` | Geopolitical/news intelligence dashboard | No functional overlap with what Foundry does. |
| `tronghieuit/tiny-tts` | 1.6M-parameter CPU text-to-speech model | No current use case (would only matter if the bridge ever spoke messages aloud — not planned). |

`virgiliojr94/book-to-skill` was also in this batch but isn't "rejected" — it's the specific
converter the blueprint's `librarian` phase already names (see the Phase 7-8 entry above);
it's still pending your explicit go-ahead, same as before this review.

## The honest summary

Everything gated on "you need an external account, a real credential, or a decision only a
human can make" stopped at that gate rather than being faked. Everything else that a phase
asked for is built and tested. If you pick a messaging provider, or want to build a native
(non-third-party) ingestion path for the knowledge pipeline, either is a reasonable next slice
— just not something to start without you weighing in first.
