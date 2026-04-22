"""Rule: device name must start with its room's area_id + a separator."""
from dataclasses import dataclass

from home_curator.policies.schema import NameStartsWithRoomPolicy
from home_curator.rules.base import Device, EvaluationContext, Issue, Severity


@dataclass
class CompiledNameStartsWithRoom:
    id: str
    enabled: bool
    severity: Severity
    separator: str
    rule_type: str = "name_starts_with_room"
    compile_error: str | None = None

    def evaluate(self, device: Device, ctx: EvaluationContext) -> Issue | None:
        if not self.enabled:
            return None
        if (device.id, self.id) in ctx.exceptions:
            return None
        if device.area_id is None:
            # Scope: only devices with an area. The missing_area rule covers
            # the no-area case separately.
            return None
        prefix = device.area_id + self.separator
        if device.display_name.startswith(prefix):
            return None
        return Issue(
            policy_id=self.id,
            rule_type=self.rule_type,
            severity=self.severity,
            message="Name Doesn't Start With Its Room",
            device_id=device.id,
        )


def compile_name_starts_with_room(p: NameStartsWithRoomPolicy) -> CompiledNameStartsWithRoom:
    return CompiledNameStartsWithRoom(
        id=p.id,
        enabled=p.enabled,
        severity=p.severity,
        separator=p.separator,
    )
