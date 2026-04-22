from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypedDict

Severity = Literal["info", "warning", "error"]


class EntitySummary(TypedDict):
    id: str
    domain: str


@dataclass(frozen=True)
class Device:
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
    state: dict[str, Any] = field(default_factory=dict)

    def to_cel_context(self) -> dict[str, Any]:
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


class CompiledPolicy(Protocol):
    id: str
    rule_type: str
    enabled: bool
    severity: Severity
    compile_error: str | None

    def evaluate(self, device: Device, ctx: EvaluationContext) -> Issue | None: ...
