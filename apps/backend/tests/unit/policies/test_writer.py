from pathlib import Path

import pytest
from ruamel.yaml import YAML

from home_curator.policies import writer
from home_curator.policies.writer import write_policies_file


def yaml_safe_load(text: str):
    return YAML(typ="safe").load(text)


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


def test_write_is_atomic_when_the_dump_fails(tmp_path: Path, monkeypatch):
    """A crash mid-write must not damage the file that is already there.

    `open("w")` truncates immediately, so writing in place left the user's
    policies empty or partial for the duration of the dump — and the file
    watcher sits on that directory, so it could read the wreckage.
    """
    path = tmp_path / "policies.yaml"
    original = "version: 1\npolicies: []\n"
    path.write_text(original)

    class _ExplodingYAML(YAML):
        def dump(self, data, stream=None, **kwargs):  # type: ignore[override]
            stream.write("version: 1\npolic")  # a partial write, then disaster
            raise RuntimeError("disk full")

    monkeypatch.setattr(writer, "YAML", _ExplodingYAML)

    with pytest.raises(RuntimeError, match="disk full"):
        write_policies_file(path, {"version": 1, "policies": [{"id": "x"}]})

    assert path.read_text() == original


def test_failed_write_leaves_no_temporary_file(tmp_path: Path, monkeypatch):
    path = tmp_path / "policies.yaml"
    path.write_text("version: 1\npolicies: []\n")

    class _ExplodingYAML(YAML):
        def dump(self, data, stream=None, **kwargs):  # type: ignore[override]
            raise RuntimeError("disk full")

    monkeypatch.setattr(writer, "YAML", _ExplodingYAML)

    with pytest.raises(RuntimeError):
        write_policies_file(path, {"version": 1, "policies": []})

    assert [p.name for p in tmp_path.iterdir()] == ["policies.yaml"]


def test_successful_write_leaves_no_temporary_file(tmp_path: Path):
    path = tmp_path / "policies.yaml"

    write_policies_file(path, {"version": 1, "policies": []})

    assert [p.name for p in tmp_path.iterdir()] == ["policies.yaml"]


def test_write_recovers_from_an_unparseable_existing_file(tmp_path: Path):
    """A file left corrupt by an older build must not block every future save.

    Comment preservation reads the existing file back; when that read failed,
    the error escaped as an unhandled 500 and the only repair was editing the
    file by hand over SSH — locking the user out of the UI that would have
    fixed it.
    """
    path = tmp_path / "policies.yaml"
    path.write_text("version: 1\npolicies: [unclosed\n")

    write_policies_file(path, {"version": 1, "policies": []})

    assert yaml_safe_load(path.read_text()) == {"version": 1, "policies": []}


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
