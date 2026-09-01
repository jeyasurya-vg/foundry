# Messaging bridge

Phase 7. Optional, provider-pluggable (Part 5.1) — Telegram is the only provider built so
far. Slack/Matrix/Discord would each add a `shell/bridge/<provider>.py` implementing the same
`Bridge` interface; nothing else in this project should need to change.

## Design constraints this holds

- **Outbound polling only.** `TelegramBridge.poll()` calls `getUpdates` — there is no inbound
  port, no webhook, no tunnel, nothing exposed to the network. This is a strictly better
  security posture than most agent gateways, and it's not a compromise: long polling is a
  first-class way to use the Telegram Bot API, not a workaround.
- **The bridge never reasons.** `shell/bridge/telegram.py` and `cli.py` route, queue, and
  render. Every decision (what to send, when, to whom) is the caller's.
- **Auth allowlist, everything else silently dropped.** `TelegramBridge` refuses to construct
  with an empty allowlist (Part 5.1: "single operator ID by default" only means something if
  there's always at least one ID configured), and `_parse_update` drops any message or button
  press from an ID not on it — no error, no reply, nothing. `tests/test_bridge.py` pins this
  down directly.
- **Approvals via inline buttons.** `send_approval_request` sends exactly the three buttons
  Part 5.1 describes: Approve / Deny / Approve and remember. `ApprovalStore`
  (`shell/bridge/approvals.py`, SQLite, same pattern as the ledger and usage tracker) tracks
  each request from `pending` to `approved`/`denied`, with a `remember` flag.
- **No hosted service, no credential relay** (compliance rule 6). The bridge talks directly
  to Telegram's API using a token you generate and hold; nothing proxies through anything
  this project runs.

## What's genuinely verified vs. what's tested

Every unit test in `tests/test_bridge.py` mocks the HTTP layer (`request_fn` dependency
injection, same pattern as `AnthropicAPIRunner`) — no network, no token needed, safe in CI.

Beyond that, this was verified against a real bot and a real Telegram account in the session
that built it: a real `getMe` confirmed the bot; a real approval-request message with three
buttons was sent to a real chat; a real button tap came back through `getUpdates`, was parsed
by the actual `TelegramBridge._parse_update`, and was resolved through the actual
`ApprovalStore.resolve()` — not simulated. One real bug surfaced doing this: failing to call
`answerCallbackQuery` promptly leaves Telegram's button stuck showing a loading spinner
client-side, which is why `cli.py poll` always answers a callback immediately after resolving
it, and why a real device test caught this rather than only a mocked one.

## CLI

```bash
python -m shell.bridge.cli --allow 965676894 send --chat-id 965676894 --text "hello"
python -m shell.bridge.cli --allow 965676894 request-approval --chat-id 965676894 \
  --text "push to main?" --ticket t-1
python -m shell.bridge.cli --allow 965676894 poll --timeout 25
python -m shell.bridge.cli list-pending
```

`--allow` is repeatable (`--allow ID --allow ID2`) or read from `FOUNDRY_BRIDGE_ALLOWLIST`
(comma-separated) so you don't have to pass it every time. The bot token comes from
`TELEGRAM_BOT_TOKEN` — set as a real environment variable, or in a local `.env` file at the
repo root (loaded by `shell/bridge/env.py`, a ~15-line stdlib-only loader — no `python-dotenv`
dependency). `.env` is gitignored (compliance rule 6: secrets never committed).

## Local machine SSL note

If Python's `urllib` fails here with `CERTIFICATE_VERIFY_FAILED` while `curl` against the
same URL succeeds, that's a local trust-store issue (commonly antivirus or corporate software
doing HTTPS inspection with a certificate OpenSSL's stricter validation rejects) — not a bug
in this code. It doesn't affect most machines. If you hit it, `curl` remains a working
diagnostic path; the bridge's own HTTP layer is a single small method
(`TelegramBridge._http_request`) if a machine-specific workaround is ever needed.

## What's not built yet

- **"Approve and remember" doesn't do anything yet beyond recording the flag.** Part 5.1's
  intent — appending the approval to the requesting agent's tool fence so the permission
  policy builds itself from real use — needs a way to safely mutate `plugin/agents/*.md`
  frontmatter, which doesn't exist. `ApprovalStore.list_remembered()` is there for whenever
  that's built; nothing reads it automatically today.
- **Channel-per-stream** (Part 5.1: one thread/topic per project or department) — the current
  CLI is single-chat, single-operator. Multi-chat routing (mapping a project or department to
  its own Telegram topic) isn't built.
- **No wiring into the ledger or scheduler yet.** Nothing calls `request-approval`
  automatically when an agent hits an irreversible action, or notifies on ticket state
  changes. The bridge is a working, verified primitive; hooking it into the pipeline's actual
  approval points (release-to-main, deletes, deploys) is the next slice.
- **Slack, Matrix, Discord** — not started. `Bridge`/`InboundMessage`/`InboundCallback` in
  `shell/bridge/base.py` are the interface any of them would implement.
