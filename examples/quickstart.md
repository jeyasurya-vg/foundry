# Quickstart

Everything below is also a runnable script — `python examples/quickstart.py` — that
`tests/test_quickstart.py` runs on every `pytest` invocation. If this walkthrough and the
script ever disagree, the script is right; file an issue against this doc.

This exercises the whole stack using only the CLI, standing in for what a department agent
does automatically when you run `/foundry:next` inside actual Claude Code. Following it end
to end takes a few minutes, not an hour — the "under an hour" gate (blueprint Part 9) is
meant as a ceiling, not a target.

## 1. Propose, greenlight, and start a project

```bash
python -m shell.ledger.cli project add --id quickstart --name "Quickstart Widget" \
  --brief "prove the pipeline works"
python -m shell.ledger.cli project greenlight quickstart --rationale "worth a demo"
python -m shell.ledger.cli project start quickstart --rationale "kicking off"
```

Every portfolio transition needs a `--rationale` — see `docs/PORTFOLIO.md`.

## 2. Add two dependent tickets

```bash
python -m shell.ledger.cli add --brief "design the widget schema" \
  --done-when "schema documented" --project quickstart
# -> note the printed "id", e.g. t-8cec994e

python -m shell.ledger.cli add --brief "build the widget" --done-when "tests pass" \
  --project quickstart --depends-on t-8cec994e
```

## 3. Walk the first ticket to done

```bash
python -m shell.ledger.cli next --project quickstart
# claims and starts the dependency-free ticket (the schema one) — the build ticket is
# invisible to `next` until its dependency reaches `done`, not just `review`

python -m shell.ledger.cli checkpoint t-8cec994e --summary "wrote the schema" \
  --artifacts '["schema.md"]' --next-step "-" --final
# -> state: review
```

`review -> done` has no CLI command by design (`docs/LEDGER.md`): approving a ticket is an
independent reviewer's job, not the CLI's. In attended mode that's another department agent;
by hand, it's the `Ledger` class directly:

```bash
python -c "from shell.ledger.ledger import Ledger; l = Ledger('company/ledger.db'); l.approve('t-8cec994e'); l.close()"
```

## 4. The dependent ticket is now claimable

```bash
python -m shell.ledger.cli next --project quickstart
# -> claims the build ticket, now that its dependency is `done`
```

Walk it to `review` and approve it the same way as step 3.

## 5. Ship the project

```bash
python -m shell.ledger.cli project ship quickstart --rationale "v1 done" --version 0.1.0
```

## 6. Look at it in Mission Control

```bash
python -m shell.console.cli
# -> http://127.0.0.1:8787 — Board and Portfolio tabs show exactly what you just did
```

## 7. Record a usage observation

```bash
python -m shell.usage.cli record --provider claude --window session --remaining 0.75 \
  --reset 2026-09-01T20:00:00+00:00
python -m shell.usage.cli status
```

`--remaining`/`--reset` are numbers you read off Claude Code's own `/usage` output — see
`docs/USAGE.md` for why this tool doesn't (and can't, compliantly) poll them itself.

## Where to go from here

- `docs/LEDGER.md` — the ticket state machine in full, and what each phase built.
- `docs/PORTFOLIO.md` — the project lifecycle and why shelving is enforced, not just advised.
- `docs/AUTONOMOUS.md` — what it'd take to run this unattended, and what's still missing.
- `docs/ROADMAP.md` — the honest list of what isn't built yet, and why.
- `CONTRIBUTING.md` — if you want to add a department, a runner, or a usage provider.
