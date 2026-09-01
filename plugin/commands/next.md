---
description: Claim the next ready ticket and dispatch it to the right department agent.
allowed-tools: Bash(python -m shell.ledger.cli *), Bash(python -m shell.usage.cli *), Task, Read
argument-hint: [project-id]
---

Claim and drive the next ready ticket through exactly one pipeline stage.

## Steps

1. Run `python -m shell.ledger.cli resume --project $ARGUMENTS` first. If it returns a ticket
   (not `{"resumable": false}`), a previous session died mid-run on it — skip straight to step
   3 using this ticket and its `last_checkpoint` as the resume packet. Do **not** re-claim it;
   it is already `running`.
2. Otherwise, run `python -m shell.ledger.cli next --project $ARGUMENTS` (drop
   `--project ...` if no argument was given). If the result is `{"ready": false}`, tell the
   user there is nothing ready right now — either the board is empty, everything left has
   unmet dependencies, or everything is blocked on quota — and stop here.
3. Read the ticket's `stage` field and dispatch to exactly one department agent via
   the `Task` tool, per the pipeline in `plugin/CLAUDE.md`:
   - `intake` / `brief` -> `product`
   - `design` -> `architect`
   - `decompose` -> `orchestrator`
   - `build` -> `engineer`
   - `test` -> `qa`
   - `security` -> `security`
   - `docs` -> `docs`
   - `review` -> whichever department did **not** do the work (independent reviewer —
     non-negotiable #2 in `plugin/CLAUDE.md`)
   - `release` -> `release`
   Give the dispatched agent the full ticket record, its `done_when` exit contract, and its
   `last_checkpoint` (if any) as the resume packet. That agent has no other context — tasks
   are the only channel between agents.
4. The dispatched agent must checkpoint after every atomic step
   (`python -m shell.ledger.cli checkpoint <id> --summary ... --artifacts ... --next-step ...`)
   before doing anything else. This is mechanically enforced by the checkpoint-gate
   `PostToolUse` hook (`plugin/hooks/checkpoint_gate.py`) — if it blocks a tool call with a
   warning, checkpoint immediately; you are not being asked twice.
5. When the dispatched agent finishes its stage, report the ticket's new state to the user in
   one or two sentences. Do not automatically claim another ticket — `/foundry:next` drives
   exactly one ticket per invocation, by design (Part 3.1: every ticket fits one usage window).

## Notes

- This command assumes `shell/ledger` is present in this repo (it is, for this deployment). A
  zero-dependency plugin-only distribution elsewhere would need a lighter ticket store; that's
  a packaging concern for a later phase, not something this command handles today.
