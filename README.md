# Foundry

An open-source framework for running a software company staffed entirely by AI agents:
product, architecture, engineering, QA, security, docs, release and ops. Agents pick up
tickets, do the work, review each other, and ship. A human sits at the board level.

Status: Phases 0-7 and 9 built — repo structure, compliance and charter docs, the ledger
(schema, state machine, CLI), `/foundry:next` wired to the plugin's agents with a
checkpoint-enforcing hook, the portfolio (`projects` table and lifecycle), a cross-provider
usage tracker, an autonomous runner + fair-share scheduler (API-key-gated, untested against a
live key), a Mission Control web console, a Telegram messaging bridge with approvals
(verified against a real bot and a real button tap), and docs/examples/contribution guide.
New here? Start with `examples/quickstart.md`. **What's not built and why:**
`docs/ROADMAP.md` — the `librarian` knowledge pipeline needs a third-party-dependency
decision only a human can make, Slack/Matrix/Discord bridges each need their own provider
setup, and a few other things are stopped at a similar real blocker rather than faked.

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
            runners/   Runner interface; AnthropicAPIRunner (API-key-gated); stubs for
                       Bedrock/Vertex/OpenAI/local — see docs/AUTONOMOUS.md.
            scheduler/ fair-share portfolio scheduler, quota-aware tick loop.
            console/   Mission Control web dashboard (loopback only) — see docs/CONSOLE.md.
            bridge/    Telegram messaging bridge + approvals — see docs/BRIDGE.md.
            Never touches OAuth credentials; API-key-first.
docs/       LEDGER.md, PORTFOLIO.md, USAGE.md, AUTONOMOUS.md, CONSOLE.md, BRIDGE.md, ROADMAP.md.
examples/   quickstart.md + a runnable quickstart.py (tests/test_quickstart.py runs it).
tests/      pytest suite for the ledger, portfolio, usage tracker, runners, scheduler,
            console, and plugin hooks.
```

Read `COMPLIANCE.md` first — it explains why the repo is split into two planes and what rules
are non-negotiable. Then `company/CHARTER.md` and `company/ORG.md` for how the company itself
operates, and `CONTRIBUTING.md` if you're adding to it.

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

## Messaging bridge

```
python -m shell.bridge.cli --allow <your-telegram-id> request-approval \
  --chat-id <your-telegram-id> --text "push to main?"
python -m shell.bridge.cli --allow <your-telegram-id> poll
```

Telegram only so far; outbound long-polling, no inbound port. Approvals arrive as
Approve/Deny/Approve-and-remember buttons. `docs/BRIDGE.md`.

## Mission Control

```
python -m shell.console.cli          # http://127.0.0.1:8787, loopback only
```

Dashboard, ticket board, portfolio lifecycle, department roster, and memory — all read
straight from the ledger/portfolio/filesystem, nothing new to configure. `docs/CONSOLE.md`.

## Attended vs. autonomous

- **Attended** (default): you run official Claude Code; the ledger tracks tickets on disk.
  No model calls originate from `shell/`.
- **Autonomous** (`shell/runners`, `shell/scheduler`): requires an explicit
  `ANTHROPIC_API_KEY`. Refuses to start without one — no fallback, no auto-detection. Built
  and unit-tested; never invoked against a live key in this repo's own history (none is set).
  `docs/AUTONOMOUS.md`.

## Quickstart

```
python examples/quickstart.py
```

Runs the whole stack end to end against a scratch database: a project through its lifecycle,
two dependent tickets through the state machine, a usage observation. Prose walkthrough with
the same commands spelled out: `examples/quickstart.md`.
