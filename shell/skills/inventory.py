"""Skill inventory: loads `plugin/skills/*/MANIFEST.json` and checks each one's `SKILL.md`
against the content hash recorded at vendor time. `docs/SKILLS.md` names this gap directly:
"check by hand", fine at 2 entries, not at 20 — this module is what makes it mechanical.

Kept independent of `shell/console` so it's usable (and testable) without the web server.
"""

import hashlib
import json
from pathlib import Path

MANIFEST_NAME = "MANIFEST.json"
SKILL_FILE_NAME = "SKILL.md"


def _skill_dirs(repo_root):
    skills_dir = Path(repo_root) / "plugin" / "skills"
    if not skills_dir.exists():
        return []
    return sorted(p.parent for p in skills_dir.glob(f"*/{MANIFEST_NAME}"))


def load_manifest(skill_dir):
    return json.loads((Path(skill_dir) / MANIFEST_NAME).read_text(encoding="utf-8"))


def verify_integrity(skill_dir):
    """Compares `SKILL.md`'s current content hash against the manifest's recorded
    `content_sha256`. Returns a result dict rather than raising — a mismatch is something to
    surface and investigate, not necessarily a crash (it might just mean the skill was
    hand-edited after vendoring and the manifest needs refreshing)."""
    skill_dir = Path(skill_dir)
    manifest = load_manifest(skill_dir)
    skill_file = skill_dir / SKILL_FILE_NAME
    expected = manifest.get("content_sha256")

    if not skill_file.exists():
        return {"ok": False, "reason": f"{SKILL_FILE_NAME} missing", "expected": expected, "actual": None}

    actual = hashlib.sha256(skill_file.read_bytes()).hexdigest()
    if expected is None:
        return {
            "ok": False, "expected": None, "actual": actual,
            "reason": "manifest has no content_sha256 to check against",
        }
    return {
        "ok": actual == expected, "expected": expected, "actual": actual,
        "reason": None if actual == expected else "SKILL.md no longer matches the manifest's recorded hash",
    }


def load_manifests(repo_root):
    """Every vendored/generated skill under `plugin/skills/`, each manifest plus its live
    integrity check — the data Mission Control's Skills screen renders."""
    skills = []
    for skill_dir in _skill_dirs(repo_root):
        manifest = load_manifest(skill_dir)
        skills.append({
            **manifest,
            "dir": str(skill_dir.relative_to(Path(repo_root))).replace("\\", "/"),
            "integrity": verify_integrity(skill_dir),
        })
    return skills
