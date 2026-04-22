"""Rule: device display name must start with its room + a separator."""
from dataclasses import dataclass
from typing import Literal

from home_curator.policies.schema import NameStartsWithRoomPolicy
from home_curator.rules.base import Device, EvaluationContext, Issue, Severity


@dataclass
class CompiledNameStartsWithRoom:
    id: str
    enabled: bool
    severity: Severity
    source: Literal["area_id", "area_name"]
    separator: str
    rule_type: str = "name_starts_with_room"
    compile_error: str | None = None

    def evaluate(self, device: Device, ctx: EvaluationContext) -> Issue | None:
        if not self.enabled:
            return None
        if (device.id, self.id) in ctx.exceptions:
            return None
        if device.area_id is None:
            return None
        room = device.area_id if self.source == "area_id" else device.area_name
        if not room:
            # area_name can still be None even with area_id set if registry
            # load is racing; skip rather than false-fire.
            return None
        prefix = room + self.separator
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
    # Separator default is resolved by the schema validator; never None here.
    assert p.separator is not None
    return CompiledNameStartsWithRoom(
        id=p.id,
        enabled=p.enabled,
        severity=p.severity,
        source=p.source,
        separator=p.separator,
    )
