from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML, YAMLError

from home_curator.policies.schema import PoliciesFile

_yaml = YAML(typ="safe")


@dataclass
class LoadResult:
    file: PoliciesFile | None
    error: str | None


def load_policies_file(path: Path) -> LoadResult:
    if not path.exists():
        return LoadResult(file=None, error=f"policies file does not exist: {path}")
    try:
        raw = _yaml.load(path.read_text())
    except YAMLError as e:
        return LoadResult(file=None, error=f"YAML syntax error: {e}")
    if raw is None:
        return LoadResult(file=None, error="policies file is empty")
    try:
        parsed = PoliciesFile.model_validate(raw)
    except ValidationError as e:
        return LoadResult(file=None, error=f"schema error: {e}")
    return LoadResult(file=parsed, error=None)
