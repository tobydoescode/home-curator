from pathlib import Path

import pytest

from home_curator.policies.loader import LoadResult, load_policies_file

FIXTURE = Path(__file__).parents[2] / "fixtures" / "sample_policies.yaml"


def test_loads_valid_file(tmp_path):
    r = load_policies_file(FIXTURE)
    assert isinstance(r, LoadResult)
    assert r.file is not None
    assert r.error is None
    assert len(r.file.policies) == 4


def test_missing_file_returns_error(tmp_path):
    r = load_policies_file(tmp_path / "missing.yaml")
    assert r.file is None
    assert "does not exist" in r.error


def test_invalid_yaml_syntax(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("version: 1\npolicies:\n  - id: x\n    type:")
    r = load_policies_file(p)
    assert r.file is None
    assert r.error


def test_invalid_schema(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("version: 1\npolicies:\n  - id: x\n    type: unknown_type\n    severity: info\n    enabled: true\n")
    r = load_policies_file(p)
    assert r.file is None
    assert "type" in r.error.lower()
