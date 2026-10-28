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
  --text "push to main?" --ticket t-1 --agent release
python -m shell.bridge.cli --allow 965676894 request-action --kind portfolio.ship \
  --project p-1 --rationale "ready" --text "ship p-1 to main?" --chat-id 965676894
python -m shell.bridge.cli --allow 965676894 poll --timeout 25
python -m shell.bridge.cli list-pending
```

`--allow` is repeatable (`--allow ID --allow ID2`) or read from `FOUNDRY_BRIDGE_ALLOWLIST`
(comma-separated) so you don't have to pass it every time. The bot token comes from
`TELEGRAM_BOT_TOKEN` — set as a real environment variable, or in a local `.env` file at the
repo root (loaded by `shell/bridge/env.py`, a ~15-line stdlib-only loader — no `python-dotenv`
dependency). `.env` is gitignored (compliance rule 6: secrets never committed).

`--chat-id` can be replaced by `--project <id>` or `--department <name>` on `send`,
`request-approval`, and `request-action` — resolved through `--channels` (default
`company/bridge_channels.json`, gitignored; see `company/bridge_channels.example.json` for
the shape). That's channel-per-stream routing: one project or department, one Telegram chat
(and, once the operator's own supergroup has Topics enabled, one `thread_id`) instead of
everything landing in a single operator chat.

## Approval points: `request-action`

`request-action --kind {portfolio.ship,portfolio.shelve,portfolio.archive}` is the actual
wiring into the ledger/portfolio the earlier version of this doc said was still missing.
Unlike `request-approval` (a free-text prompt a human has to act on separately),
`request-action` records a structured `(kind, payload)` on the approval row; `poll` applies
it automatically — calling the real `Portfolio.ship`/`shelve`/`archive` — the moment the
request resolves `approved` (see `shell/bridge/actions.py`). A denied or still-pending
request never touches the portfolio. `Portfolio.ship`/`shelve`/`archive` stay directly
callable exactly as before; this is an additional gated path, not a replacement.

## "Approve and remember"

`--agent <name>` on `request-approval`/`request-action` names which agent's fence the
"remember" button should update. On `poll`, a resolved `approved, remember=True` request
with an `agent` set calls `shell/bridge/fence.remember()`, which appends the request's text
to that agent's frontmatter `remembered:` list (`.claude/agents/<name>.md` if a
project-level copy exists — where Claude Code actually enforces a `Bash(...)`-qualified
fence — else the plugin-shipped `plugin/agents/<name>.md`, where it's a human-reviewable
note, same honesty as every agent file's own caveat that plugin-level `tools:` can't be
fenced to specific commands). Idempotent: the same note recorded twice doesn't duplicate.

## Local machine SSL note

If Python's `urllib` fails here with `CERTIFICATE_VERIFY_FAILED` while `curl` against the
same URL succeeds, that's a local trust-store issue (commonly antivirus or corporate software
doing HTTPS inspection with a certificate OpenSSL's stricter validation rejects) — not a bug
in this code. It doesn't affect most machines. If you hit it, `curl` remains a working
diagnostic path; the bridge's own HTTP layer is a single small method
(`TelegramBridge._http_request`) if a machine-specific workaround is ever needed.

## What's not built yet

- **Still manual, not automatic.** `request-action` has to be invoked explicitly by whatever
  is driving a ticket/project forward (a human, or a dispatched agent via `Bash`) — nothing
  in `shell/ledger`/`shell/scheduler` calls it on its own when a ticket reaches a release or
  delete point. The approval points exist and apply themselves once approved; deciding *when*
  to call them is still the caller's job.
- **"Approve and remember" doesn't feed back into platform-enforced permissions** for a
  plugin-shipped agent — it can't; Claude Code only enforces a `Bash(...)`-qualified fence
  for a project-level `.claude/agents/*.md` copy, not a plugin one. `fence.remember()`
  targets that project-level copy first when it exists, so the enforcement gap is the
  platform's, not this code's.
- **No notifications on plain ticket state changes** (e.g. "ticket t-1 just failed") — the
  bridge only ever speaks when something calls `send`/`request-approval`/`request-action`
  explicitly.
- **Slack, Matrix, Discord** — not started. `Bridge`/`InboundMessage`/`InboundCallback` in
  `shell/bridge/base.py` are the interface any of them would implement; `thread_id` on
  `send`/`send_approval_request` is Telegram-specific today (maps to `message_thread_id`) —
  another provider would need its own equivalent, if it has one.
