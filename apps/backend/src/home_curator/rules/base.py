"""Shared types for the rule engine."""
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypedDict, runtime_checkable

Severity = Literal["info", "warning", "error"]


class EntitySummary(TypedDict, total=True):
    id: str
    domain: str


@dataclass
class Device:
    """One HA device, enriched with `state` for rule evaluation.

    Not frozen: `entities` and `state` are mutable collections and the class
    is never placed in a set. Prefer constructing a new Device rather than
    mutating one in place.
    """

    id: str
    name: str
    name_by_user: str | None
    manufacturer: str | None
    model: str | None
    area_id: str | None
    area_name: str | None
    integration: str | None
    disabled_by: str | None
    entities: list[EntitySummary]
    # HA registry timestamps (ISO-8601 strings). Optional because older HA
    # versions don't emit them; surfaced through the API for display only.
    created_at: str | None = None
    modified_at: str | None = None
    state: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        """What the HA user sees — their override (`name_by_user`) if set,
        otherwise the integration's default (`name`)."""
        return self.name_by_user or self.name

    def to_cel_context(self) -> dict[str, Any]:
        """Dict form consumed by `custom_cel` policies.

        Note: the `state` attribute is surfaced under the key `_state` so
        that CEL expressions can distinguish computed fields (set by the
        deletion tracker, etc.) from the device's own attributes.
        """
        return {
            "id": self.id,
            "name": self.name,
            "name_by_user": self.name_by_user,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "area_id": self.area_id,
            "area_name": self.area_name,
            "integration": self.integration,
            "disabled_by": self.disabled_by,
            "entities": list(self.entities),
            "_state": dict(self.state),
        }


@dataclass(frozen=True)
class Issue:
    policy_id: str
    rule_type: str
    severity: Severity
    message: str
    device_id: str


@dataclass
class EvaluationContext:
    area_name_to_id: dict[str, str]  # lowercased name → area_id
    area_id_to_name: dict[str, str]
    exceptions: set[tuple[str, str]]  # (device_id, policy_id)

    def resolve_area_id_from_name(self, name: str) -> str | None:
        return self.area_name_to_id.get(name.lower())


@runtime_checkable
class CompiledPolicy(Protocol):
    id: str
    rule_type: str
    enabled: bool
    severity: Severity
    compile_error: str | None

    def evaluate(self, device: Device, ctx: EvaluationContext) -> Issue | None: ...
