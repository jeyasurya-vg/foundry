"""A tiny `.env` loader — stdlib only, on purpose (see CONTRIBUTING.md's dependency policy).

Not a general-purpose dotenv implementation: just enough to read `KEY=VALUE` lines into
`os.environ` without overwriting anything already set there (an explicit environment variable
always wins over a file, matching how every other credential in this project is read).
"""

import os
from pathlib import Path


def load_dotenv(path=".env"):
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
