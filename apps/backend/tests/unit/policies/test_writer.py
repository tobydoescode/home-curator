from pathlib import Path

import pytest

from home_curator.policies.writer import write_policies_file


def test_write_creates_file(tmp_path):
    path = tmp_path / "policies.yaml"
    data = {
        "version": 1,
        "policies": [
            {"id": "a", "type": "missing_area", "enabled": True, "severity": "warning"},
        ],
    }
    write_policies_file(path, data)
    text = path.read_text()
    assert "version: 1" in text
    assert "id: a" in text


def test_write_preserves_comments_in_existing_file(tmp_path):
    path = tmp_path / "policies.yaml"
    path.write_text(
        "# Top-of-file comment\n"
        "version: 1\n"
        "policies:\n"
        "  - id: keep-me\n"
        "    type: missing_area\n"
        "    enabled: true\n"
        "    severity: warning\n"
    )
    updated = {
        "version": 1,
        "policies": [
            {"id": "keep-me", "type": "missing_area", "enabled": False, "severity": "warning"},
        ],
    }
    write_policies_file(path, updated)
    text = path.read_text()
    assert "# Top-of-file comment" in text
    assert "enabled: false" in text


def test_write_creates_a_missing_parent_directory(tmp_path: Path):
    """Under the addon the parent is /config/home-curator, which does not
    exist on a fresh install and which nothing else creates. Refusing here
    meant the very first policy save returned a 500."""
    path = tmp_path / "missing" / "nested" / "policies.yaml"

    write_policies_file(path, {"version": 1, "policies": []})

    assert path.is_file()
    assert "version: 1" in path.read_text()


def test_write_surfaces_an_unwritable_parent(tmp_path: Path):
    """A read-only config mount must still raise rather than silently no-op."""
    parent = tmp_path / "readonly"
    parent.mkdir()
    parent.chmod(0o500)
    try:
        with pytest.raises(OSError):
            write_policies_file(parent / "sub" / "policies.yaml", {"version": 1, "policies": []})
    finally:
        parent.chmod(0o700)
