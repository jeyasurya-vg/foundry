import json
from pathlib import Path

from shell.skills import inventory


def test_load_manifests_finds_real_vendored_skills():
    repo_root = Path(__file__).resolve().parents[1]
    skills = inventory.load_manifests(repo_root)
    slugs = {s["slug"] for s in skills}
    assert slugs == {"taste-skill", "no-ai-slop"}


def test_load_manifests_empty_when_no_skills_dir(tmp_path):
    assert inventory.load_manifests(tmp_path) == []


def test_real_skills_pass_integrity_check():
    repo_root = Path(__file__).resolve().parents[1]
    for skill in inventory.load_manifests(repo_root):
        assert skill["integrity"]["ok"] is True, skill


def _write_skill(repo_root, slug, skill_md_text, manifest_extra=None):
    skill_dir = Path(repo_root) / "plugin" / "skills" / slug
    skill_dir.mkdir(parents=True)
    # write_bytes (not write_text) so no platform newline translation changes the hash.
    (skill_dir / "SKILL.md").write_bytes(skill_md_text.encode("utf-8"))
    manifest = {"slug": slug, "skill_name": slug, "origin": "vendored"}
    manifest.update(manifest_extra or {})
    (skill_dir / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    return skill_dir


def test_verify_integrity_detects_tampering(tmp_path):
    import hashlib
    original = "---\nname: x\n---\nbody"
    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
    skill_dir = _write_skill(tmp_path, "tampered", original, {"content_sha256": digest})

    assert inventory.verify_integrity(skill_dir)["ok"] is True

    (skill_dir / "SKILL.md").write_bytes("---\nname: x\n---\ntampered body".encode("utf-8"))
    result = inventory.verify_integrity(skill_dir)
    assert result["ok"] is False
    assert result["expected"] == digest


def test_verify_integrity_flags_missing_hash(tmp_path):
    skill_dir = _write_skill(tmp_path, "no-hash", "---\nname: x\n---\nbody")
    result = inventory.verify_integrity(skill_dir)
    assert result["ok"] is False
    assert "content_sha256" in result["reason"]


def test_verify_integrity_flags_missing_skill_file(tmp_path):
    skill_dir = Path(tmp_path) / "plugin" / "skills" / "broken"
    skill_dir.mkdir(parents=True)
    (skill_dir / "MANIFEST.json").write_text(json.dumps({"slug": "broken"}), encoding="utf-8")
    result = inventory.verify_integrity(skill_dir)
    assert result["ok"] is False
    assert "missing" in result["reason"]
