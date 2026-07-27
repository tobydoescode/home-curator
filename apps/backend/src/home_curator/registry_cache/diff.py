"""What changed between two loads of a registry cache."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Diff:
    """Ids added, removed and changed since the previous load.

    Shared by the device and entity caches: both answered the same question
    with their own identical copy of this type, so a caller handling one
    could not be type-checked against the other.
    """

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
