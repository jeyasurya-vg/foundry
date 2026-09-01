"""Part 5.1: "Auth allowlist. Single operator ID by default. Everything else silently dropped."

A pure function, deliberately: the bridge's most safety-critical check should be trivial to
read and trivial to test in isolation, not buried inside HTTP-handling code.
"""


def is_allowed(user_id, allowlist):
    """`user_id` and entries in `allowlist` are compared as strings — Telegram/Slack/etc. IDs
    arrive as numbers over the wire but are easiest to configure and compare as strings, and
    this avoids a class of bugs where "965676894" and 965676894 silently fail to match."""
    return str(user_id) in {str(a) for a in allowlist}
