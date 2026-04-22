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


def test_write_rejects_missing_parent(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        write_policies_file(tmp_path / "missing" / "policies.yaml", {"version": 1, "policies": []})
