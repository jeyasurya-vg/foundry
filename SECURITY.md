# Security

## Reporting

If you find a security issue, please open a private report rather than a public issue. Do not
include a working exploit; a description of the class of problem and how to reproduce its
effects is enough to act on.

## What this project treats as a threat

Agent frameworks fail on supply chain and prompt injection far more often than on model
quality. Foundry's posture:

- **Skills and plugins are never auto-loaded.** Every third-party skill requires an explicit
  allowlist entry: a source URL, a pinned commit, a recorded permission surface, and a periodic
  integrity re-check. A skill is markdown that instructs an agent with shell access — treat it
  as code you are about to run, because it is.
- **Content-fetching agents are read-only.** Any agent that reads external content (web,
  issues, email, repos) gets a read-only fence and cannot write to memory. Fetched content is
  never distilled into `company/MEMORY.md` or promoted to `company/knowledge/`.
- **Irreversible actions always require human approval**, regardless of what any fetched
  content says.
- **Sandboxing.** Code work happens in a dedicated worktree per ticket. Autonomous mode
  (`shell/`) is designed to run in a container with no host mounts.
  `--dangerously-skip-permissions` is documented as container-only and is never a default.
- **Secrets never live in config files.** Environment variables or a secrets manager only. A
  pre-commit secret scan runs on the workspace.
- **Auditability.** Every ledger mutation writes an append-only event row in the same
  transaction (`docs/LEDGER.md`). Every agent action is traceable to a ticket, a checkpoint and
  a commit.
- **Injection test as a release gate.** The knowledge pipeline (`librarian`, planned) ships a
  fixture containing an embedded instruction and CI asserts the agent ignores it, not just that
  it "usually" does.

See `COMPLIANCE.md` for the separate set of rules governing credentials and model-provider use.
