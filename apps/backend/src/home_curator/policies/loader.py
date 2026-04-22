"""Load and validate `policies.yaml` into a `PoliciesFile`."""
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML, YAMLError

from home_curator.policies.schema import PoliciesFile


@dataclass
class LoadResult:
    file: PoliciesFile | None
    error: str | None


def load_policies_file(path: Path) -> LoadResult:
    """Load + validate a policies YAML file.

    Returns a LoadResult where exactly one of (file, error) is populated.
    A fresh YAML parser instance is used per call so that concurrent callers
    (hot-reload + startup) cannot corrupt shared parser state.
    """
    if not path.exists():
        return LoadResult(file=None, error=f"policies file does not exist: {path}")
    yaml = YAML(typ="safe")
    try:
        text = path.read_text()
    except OSError as e:
        return LoadResult(file=None, error=f"cannot read policies file: {e}")
    try:
        raw = yaml.load(text)
    except YAMLError as e:
        return LoadResult(file=None, error=f"YAML syntax error: {e}")
    if raw is None:
        return LoadResult(file=None, error="policies file is empty")
    try:
        parsed = PoliciesFile.model_validate(raw)
    except ValidationError as e:
        return LoadResult(file=None, error=f"schema error: {e}")
    return LoadResult(file=parsed, error=None)
