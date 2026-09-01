"""Static registry of usage-tracked providers.

Each provider declares the rolling windows it exposes and a `status`:

- "active"  — this tool can record and report real observations for it.
- "stub"    — no data source is wired up yet; `record`/`status` say so plainly
              rather than inventing numbers.

Adding a provider is a data change here, not a code change elsewhere.
"""

PROVIDERS = {
    "claude": {
        "label": "Claude (Pro/Max via Claude Code)",
        "windows": ("session", "weekly"),
        "status": "active",
        "note": (
            "No compliant API exposes Claude Code's subscription quota "
            "(the 5h/weekly rate-limit headers only appear on Anthropic API "
            "responses, and reading them would require reusing the Claude "
            "Code OAuth session token outside the official client, which "
            "COMPLIANCE.md forbids). Record observations from Claude Code's "
            "own `/usage` output instead."
        ),
    },
    "codex": {
        "label": "ChatGPT Codex",
        "windows": ("session", "weekly"),
        "status": "stub",
        "note": "Not configured. Codex CLI was not found on this machine.",
    },
    "ollama_cloud": {
        "label": "Ollama Cloud API",
        "windows": ("monthly",),
        "status": "stub",
        "note": "Not configured. Needs an ollama.com cloud API key.",
    },
}


def get_provider(name):
    if name not in PROVIDERS:
        raise KeyError(f"unknown provider: {name} (known: {sorted(PROVIDERS)})")
    return PROVIDERS[name]


def is_stub(name):
    return get_provider(name)["status"] == "stub"


def valid_window(name, window):
    return window in get_provider(name)["windows"]
