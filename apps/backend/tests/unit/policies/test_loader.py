from pathlib import Path

from home_curator.policies.loader import LoadResult, load_policies_file

FIXTURE = Path(__file__).parents[2] / "fixtures" / "sample_policies.yaml"


def test_loads_valid_file():
    r = load_policies_file(FIXTURE)
    assert isinstance(r, LoadResult)
    assert r.file is not None
    assert r.error is None
    # Fixture has 4 policies; loader merges any missing baselines. The
    # fixture already has the three device baselines, so only the three
    # entity baselines are appended → 4 + 3 = 7.
    assert len(r.file.policies) == 7
    ids = {p.id for p in r.file.policies}
    # Fixture-original ids survive.
    assert {"naming-convention", "missing-room", "reappeared", "aqara-needs-room"} <= ids
    # Entity baselines were merged in.
    assert {"entity-naming-convention", "entity-missing-area", "entity-reappeared"} <= ids


def test_missing_file_returns_default_policies(tmp_path):
    # First-run of the addon: no policies.yaml on disk yet. The loader
    # seeds six built-in rules so both Device and Entity settings have
    # something to render. The user tweaks / removes via the UI.
    r = load_policies_file(tmp_path / "missing.yaml")
    assert r.error is None
    assert r.file is not None
    assert r.file.version == 1
    types = {p.type for p in r.file.policies}
    assert types == {
        "naming_convention", "missing_area", "reappeared_after_delete",
        "entity_naming_convention", "entity_missing_area",
    }


def test_invalid_yaml_syntax(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("key: [unclosed\n")  # genuine YAML parse error
    r = load_policies_file(p)
    assert r.file is None
    assert r.error is not None
    assert "YAML syntax error" in r.error


def test_unreadable_file_returns_error(tmp_path):
    p = tmp_path / "locked.yaml"
    p.write_text("version: 1\npolicies: []\n")
    p.chmod(0o000)
    try:
        r = load_policies_file(p)
    finally:
        p.chmod(0o600)  # restore so pytest can clean up
    assert r.file is None
    assert r.error is not None
    assert "cannot read" in r.error


def test_invalid_schema(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(
        "version: 1\n"
        "policies:\n"
        "  - id: x\n"
        "    type: unknown_type\n"
        "    severity: info\n"
        "    enabled: true\n"
    )
    r = load_policies_file(p)
    assert r.file is None
    assert r.error is not None
    assert "type" in r.error.lower()
