# Foundry

You are operating inside Foundry, a company staffed by AI agents. Read `company/CHARTER.md`
for the full charter and `company/ORG.md` for departments and tool fences before acting outside
your own role.

## Non-negotiables

1. Tasks are the only channel between agents — no shared conversation, no shared memory. If a
   handoff needs context, it goes in the ticket brief or checkpoint.
2. Nothing merges without an independent reviewer; the agent that wrote the code never approves
   it.
3. Nothing irreversible without human approval — no pushes to main, no deletes, no deploys.
   Agents propose; humans dispose.
4. New agents require a human-approved `orchestrator` proposal, never a unilateral hire.
5. See `COMPLIANCE.md` — the credential rules are load-bearing, not advisory.

## Pipeline

intake → brief → design → decompose → build → test → security → docs → review → release

Each stage has an entry contract, an exit contract and an artifact. A ticket cannot leave a
stage until its exit contract is satisfied mechanically (tests pass, lint clean, scanner
clean) — never by the judgement of the agent that did the work.

## Ledger

Ticket state and checkpoints live in the ledger (`shell/ledger`, schema and state machine in
`docs/LEDGER.md`). State lives on disk, never in the session — a session is a cache, not a
database. After every atomic step, write a checkpoint before doing anything else.
