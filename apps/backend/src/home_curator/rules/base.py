"""Shared types for the rule engine."""
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypedDict, runtime_checkable

Severity = Literal["info", "warning", "error"]
TargetKind = Literal["device", "entity"]


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


@dataclass
class Entity:
    """One HA entity, enriched with `state` for rule evaluation.

    Mirrors `Device`'s shape. `area_id` is the entity's own override — when
    None, rules that need an effective area fall back to the owning device's
    area_id (unless the policy opts into strict mode).
    """

    entity_id: str
    name: str | None
    original_name: str | None
    icon: str | None
    domain: str
    platform: str
    device_id: str | None
    area_id: str | None
    area_name: str | None
    disabled_by: str | None
    hidden_by: str | None
    unique_id: str | None
    created_at: str | None = None
    modified_at: str | None = None
    state: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.name or self.original_name or self.entity_id

    # Intentionally NO to_cel_context() here — the entity CEL context shape
    # (entity.device embedded) is plan 2 (rules + CEL scope dispatch).


@dataclass(frozen=True)
class Issue:
    policy_id: str
    rule_type: str
    severity: Severity
    message: str
    # Discriminated target: device rules emit ("device", device.id), entity
    # rules emit ("entity", entity.entity_id). Mirrors the exception 3-tuple
    # shape so downstream consumers (API, SSE) can route issues without
    # inferring kind from rule_type.
    target_kind: TargetKind
    target_id: str


@dataclass
class EvaluationContext:
    area_name_to_id: dict[str, str]  # lowercased name → area_id
    area_id_to_name: dict[str, str]
    # Discriminated exception set: the first element is the target kind
    # ("device" or "entity") so device and entity exceptions can coexist
    # without their ids colliding. Compiled rules look up their own scope's
    # key.
    exceptions: set[tuple[TargetKind, str, str]]

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
