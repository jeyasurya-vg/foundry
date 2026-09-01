# Usage tracker

Tracks quota/session/weekly limits across AI providers (`shell/usage`). Same shape as the
ticket ledger — a small SQLite-backed CLI — for a reason: there is no compliant way to poll
live "how much quota is left" for any of these three providers.

## Why self-logged, not polled

- **Claude (Pro/Max via Claude Code).** Anthropic's `anthropic-ratelimit-unified-5h-*` and
  `-7d-*` response headers carry exactly this data, but only on responses to real Anthropic
  API calls made with the account's own OAuth session token. Extracting that token from
  `~/.claude/.credentials.json` and firing requests at `api.anthropic.com` outside the
  official client is the precise pattern `COMPLIANCE.md` (Part 1.4, rule 1) forbids, and is
  very likely a subscription ToS violation regardless. So: no live polling for Claude.
- **ChatGPT Codex.** Not installed on the machine this was built on, and the same
  OAuth-outside-the-client problem would apply if it were.
- **Ollama Cloud API.** No account/API key configured yet. When there is one, this is the one
  provider where a real key-based usage API call would be legitimate (it's not an OAuth
  subscription session) — see `shell/usage/providers.py` to wire it in.

So instead: you read the number Claude Code's own `/usage` output (or any provider's own UI)
already shows you, and hand it to this tool. It remembers it, computes time-until-reset, and
gives you one place to check across providers instead of three.

## Providers

| Provider | Windows | Status |
|---|---|---|
| `claude` | `session` (5h), `weekly` (7d) | active — self-logged |
| `codex` | `session`, `weekly` | stub — not configured |
| `ollama_cloud` | `monthly` | stub — needs an API key |

`shell/usage/providers.py` is the registry. Adding a provider or window is a data change
there, not new code elsewhere. A "stub" provider still appears in `status` output, clearly
marked, rather than being silently absent.

## CLI

```bash
# after checking Claude Code's own /usage command:
python -m shell.usage.cli record --provider claude --window session \
  --remaining 0.58 --reset 2026-09-01T17:00:00Z

python -m shell.usage.cli record --provider claude --window weekly \
  --remaining 0.81 --reset 2026-09-05T00:00:00Z --note "checked after standup"

python -m shell.usage.cli status                 # all providers
python -m shell.usage.cli status --provider claude
python -m shell.usage.cli providers               # what's active vs stub
```

`status` output includes `seconds_until_reset` computed from the last recorded `reset_at`
against wall-clock time — that arithmetic is live even though the underlying number isn't.

## Session boundary tracking

`plugin/hooks/hooks.json` wires a `SessionStart`/`SessionEnd` hook
(`plugin/hooks/session_log.py`) that calls `log-session` automatically:

```bash
python -m shell.usage.cli log-session --provider claude --event start --session-id <id>
python -m shell.usage.cli log-session --provider claude --event end --session-id <id>
```

This is a rough elapsed-active-time proxy alongside real `/usage` observations — never a
substitute for one. It's best-effort: if `shell/` isn't present (a plugin-only install
elsewhere), the hook fails silently rather than blocking the session.

## Adding a real API-backed provider

`ollama_cloud` is the template for this. Once you have an API key:

1. Flip its `status` to `"active"` in `providers.py`.
2. Give `UsageTracker.record()` a `source="ollama_cloud_api"` caller that does the actual HTTP
   call and feeds the result through the same `record()` method — the schema doesn't change,
   only where the numbers come from.
3. Never do this for a subscription OAuth session (Claude, and Codex if it ever ships one) —
   see "Why self-logged, not polled" above. That line does not move.
