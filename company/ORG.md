# Org chart

Nine departments. Each is a subagent definition in `plugin/agents/` with a tool fence, a
definition of done, and a handoff contract. Roles are data, not code — add your own by
dropping in a file and filing a hiring proposal (see below).

| Agent | Owns | Tool fence |
|---|---|---|
| [`chief-of-staff`](../plugin/agents/chief-of-staff.md) | Sole human interface. Intake, clarification, status. Never builds. | Read, Write, Task |
| [`orchestrator`](../plugin/agents/orchestrator.md) | Decomposition, assignment, dynamic hiring proposals | Read, Write, Task |
| [`product`](../plugin/agents/product.md) | Briefs, specs, acceptance criteria | Read, Write, WebSearch |
| [`architect`](../plugin/agents/architect.md) | System design, ADRs, interface contracts | Read, Write |
| [`engineer`](../plugin/agents/engineer.md) | Implementation, in a worktree, on a branch | Read, Edit, Write, Bash(git/npm/pytest) |
| [`qa`](../plugin/agents/qa.md) | Test authoring, coverage, regression | Read, Write, Bash(test runners) |
| [`security`](../plugin/agents/security.md) | Threat model, dependency and secret scanning, review | Read, Bash(scanners), Write |
| [`docs`](../plugin/agents/docs.md) | READMEs, changelogs, API docs, retros | Read, Write |
| [`release`](../plugin/agents/release.md) | Versioning, changelog assembly, tagging, PR | Read, Bash(git), Write |

## Planned (not yet built)

| Agent | Owns | Tool fence | Arrives in |
|---|---|---|---|
| `librarian` | Converts source corpora into agent skills (knowledge pipeline) | Read, Write, Bash(converters), **no network** | Phase 7 — see `docs/LEDGER.md` build order |

## Two invariants

- **Tasks are the only channel between agents.** No shared conversation, no shared memory. If
  a handoff needs context, it goes in the ticket.
- **Nothing merges without an independent reviewer.** The agent that wrote the code never
  approves it.

## Dynamic hiring

When `orchestrator` meets work no department owns, it drafts a new agent definition and an
`ORG.md` entry, then files an approval request. A human approves. On approval the file is
committed and the agent exists. Agents never hire agents unilaterally — this is a governance
control, and it's also what stops the org from ballooning into forty half-defined roles.
