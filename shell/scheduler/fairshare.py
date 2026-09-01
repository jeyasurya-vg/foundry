"""Fair-share portfolio scheduling (addendum Part 12.2, 12.4).

`score()` and the mode filters are pure functions on plain dicts — easy to test without a
database. `next_ticket()` wires them to the real ledger/portfolio.
"""

MODES = ("focus", "balanced", "maintenance", "discovery")


def score(project, consumed_share):
    """Weighted fair share: priority, corrected by how much of its window allocation the
    project has already consumed. A project that has used its allocation scores lower until
    the window resets, regardless of priority — this is what stops one busy project from
    starving the rest."""
    budget_share = max(project.get("budget_share") or 0.0, 0.01)
    return project["priority"] * (1.0 - min(consumed_share / budget_share, 1.0))


def eligible_projects(projects, mode):
    if mode == "focus":
        active = [p for p in projects if p["state"] == "active"]
        if not active:
            return []
        return [max(active, key=lambda p: p["priority"])]
    if mode == "balanced":
        return [p for p in projects if p["state"] in ("active", "maintained")]
    if mode == "maintenance":
        return [p for p in projects if p["state"] == "maintained"]
    if mode == "discovery":
        return [p for p in projects if p["state"] in ("proposed", "greenlit")]
    raise ValueError(f"unknown portfolio mode: {mode!r} (known: {MODES})")


def next_ticket(ledger, portfolio, runner, mode="balanced", window_consumed=None):
    """The next ticket to run, across every eligible project, or None.

    `window_consumed(project_id) -> float in [0, 1]` reports how much of the current window
    a project has already used; defaults to always 0 (no consumption tracked) if omitted,
    which degrades gracefully to pure priority ordering. See docs/AUTONOMOUS.md for how a
    real implementation would source this from shell/usage.
    """
    if not runner.headroom():
        return None

    window_consumed = window_consumed or (lambda project_id: 0.0)
    candidates = []
    for project in eligible_projects(portfolio.list_projects(), mode):
        if ledger.wip_count(project["id"]) >= project["wip_limit"]:
            continue
        ticket = ledger.next_ready(project_id=project["id"])
        if ticket:
            candidates.append((score(project, window_consumed(project["id"])), ticket))

    if not candidates:
        return None
    return max(candidates, key=lambda pair: pair[0])[1]
