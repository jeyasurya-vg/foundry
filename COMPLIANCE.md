# Compliance

Foundry runs AI agents against Claude Code and, optionally, other model providers. This
document exists so a reviewer at any vendor can read it in two minutes and see that this
project is not attempting to arbitrage its terms of service.

## The rule that shapes the architecture

Subscription (OAuth) credentials for Claude Free, Pro and Max are reserved for Anthropic's
own surfaces and may not be used by third-party tools or services. Foundry is split into two
planes specifically so it never has to cross that line:

- **Plane 1 — the company** (`plugin/`, `company/`) is pure Claude Code artifacts: agents,
  skills, commands, hooks. It has no wrapper and no harness. When you use it, you are running
  official Claude Code yourself, and your subscription applies exactly as Anthropic intends.
- **Plane 2 — the operations shell** (`shell/`, optional) is provider-agnostic and API-key-first.
  It never touches OAuth.

## Rules, enforced in code

1. **Never read, extract, copy, refresh or inject OAuth credentials.** No code path in this
   repository touches `~/.claude/`, `~/.config/claude/`, OS keychains, or any other credential
   store. This is the bright line. CI greps source for violations of it on every push.
2. **Autonomous mode requires an explicit API key.** If `ANTHROPIC_API_KEY` (or a Bedrock /
   Vertex / other provider credential) is absent, autonomous mode refuses to start and prints
   the attended-mode instructions instead. No fallback, no auto-detection.
3. **No subscription marketing.** Nothing in this repository frames Foundry as a way to use a
   subscription in place of paying for the API.
4. **Concurrency defaults to 1.** Raising it is an explicit, documented, per-user choice, never
   a shipped default.
5. **Respect backoff.** On a 429 or a limit message: stop, honour the stated reset, add jitter,
   never retry-storm. A capped exponential backoff with a hard ceiling, always.
6. **No hosted service, no proxy, no credential relay.** Foundry never handles anyone else's
   credentials. Self-hosted only, always.
7. **No telemetry.**
8. **Provider-agnostic by construction.** Anthropic is one runner among several
   (`shell/runners/`). A project that can only exist by consuming one vendor's subsidy is a
   project with a deadline.
9. **This document.** Kept in the repo root, kept current, kept plain.

## What this means in practice

- If you're running Foundry attended, through official Claude Code, none of this changes how
  you already use Claude Code. Plane 1 alone is a complete, working company.
- If you enable the autonomous shell, you provide your own API key and accept normal API
  billing. The shell will refuse to run otherwise.
