from dataclasses import dataclass

from home_curator.policies.schema import EntityMissingAreaPolicy, MissingAreaPolicy
from home_curator.rules.base import (
    Device,
    Entity,
    EvaluationContext,
    Issue,
    Severity,
    TargetScope,
)


@dataclass
class CompiledMissingArea:
    id: str
    enabled: bool
    severity: Severity
    rule_type: str = "missing_area"
    scope: TargetScope = "devices"
    compile_error: str | None = None

    def evaluate(self, thing: object, ctx: EvaluationContext) -> Issue | None:
        if not self.enabled:
            return None
        assert isinstance(thing, Device)
        device = thing
        if ("device", device.id, self.id) in ctx.exceptions:
            return None
        if device.area_id is None:
            return Issue(
                policy_id=self.id,
                rule_type=self.rule_type,
                severity=self.severity,
                message="Device Not Assigned To A Room",
                target_kind="device",
                target_id=device.id,
            )
        return None


def compile_missing_area(p: MissingAreaPolicy) -> CompiledMissingArea:
    return CompiledMissingArea(id=p.id, enabled=p.enabled, severity=p.severity)


@dataclass
class CompiledEntityMissingArea:
    id: str
    enabled: bool
    severity: Severity
    require_own_area: bool
    rule_type: str = "entity_missing_area"
    scope: TargetScope = "entities"
    compile_error: str | None = None

    def evaluate(self, thing: object, ctx: EvaluationContext) -> Issue | None:
        if not self.enabled:
            return None
        assert isinstance(thing, Entity)
        entity = thing
        if ("entity", entity.entity_id, self.id) in ctx.exceptions:
            return None

        entity_area = entity.area_id
        if self.require_own_area:
            missing = entity_area is None
        else:
            # Lenient mode — device fallback counts: an entity without its
            # own area is still fine if the owning device has one.
            device_area: str | None = None
            if entity.device_id and entity.device_id in ctx.devices_by_id:
                device_area = ctx.devices_by_id[entity.device_id].area_id
            missing = entity_area is None and device_area is None

        if missing:
            return Issue(
                policy_id=self.id,
                rule_type=self.rule_type,
                severity=self.severity,
                message="Entity Not Assigned To A Room",
                target_kind="entity",
                target_id=entity.entity_id,
            )
        return None


def compile_entity_missing_area(p: EntityMissingAreaPolicy) -> CompiledEntityMissingArea:
    return CompiledEntityMissingArea(
        id=p.id, enabled=p.enabled, severity=p.severity,
        require_own_area=p.require_own_area,
    )
