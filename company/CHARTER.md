# Foundry — Charter

## What this is

Foundry is a software company staffed entirely by AI agents: product, architecture,
engineering, QA, security, docs, release and ops (`ORG.md`). Agents pick up tickets, do the
work, review each other, and ship. A human sits at the board level — approving hires,
irreversible actions, and releases.

## How it operates

### Pipeline

```
intake → brief → design → decompose → build → test → security → docs → review → release
```

Every stage has an entry contract, an exit contract, and an artifact. A ticket cannot leave a
stage until its exit contract is satisfied, and the check is mechanical — tests pass, lint
clean, scanner clean — never a judgement call by the agent that did the work.

### Invariants

- **Tasks are the only channel between agents.** No shared conversation, no shared memory. If
  a handoff needs context, it goes in the ticket.
- **Nothing merges without an independent reviewer.** The agent that wrote the code never
  approves it.
- **Agents never hire agents unilaterally.** `orchestrator` may draft a new department when it
  meets work no one owns, but only a human approval commits the new agent file and its
  `ORG.md` entry.
- **Nothing irreversible without approval.** No pushes to main, no deletes, no deploys. Agents
  propose; humans dispose.

### Operating modes

| Mode | Who executes | Auth | Unattended? |
|---|---|---|---|
| Attended (default) | Official Claude Code, driven by the human | Subscription, natively | No |
| Autonomous (`shell/`, optional) | The shell's runner | Explicit API key | Yes |

In attended mode the ledger tracks work on disk and you drive execution yourself through
Claude Code. Orchestration lives in the ledger; execution lives in Anthropic's client (or, in
autonomous mode, in a provider runner under `shell/runners/`).

### Definition of done

A ticket is done when: its `done_when` exit contract passes mechanically, an independent
department reviewed it, and a checkpoint records the resulting artifacts (file paths, commit
SHA). Full state machine: `../docs/LEDGER.md`.

### Memory

Three layers, all on disk, all in git: raw session logs (`logs/`), curated project memory
(`MEMORY.md`, hard-capped, read at session start), and the durable knowledge base
(`knowledge/`, navigated by `knowledge/INDEX.md`, never loaded wholesale). Nothing but the
memory curator writes to `MEMORY.md`. Every memory write is its own reviewable commit.
