from dataclasses import dataclass

from home_curator.policies.schema import MissingAreaPolicy
from home_curator.rules.base import Device, EvaluationContext, Issue, Severity


@dataclass
class CompiledMissingArea:
    id: str
    enabled: bool
    severity: Severity
    rule_type: str = "missing_area"
    scope: str = "devices"
    compile_error: str | None = None

    def evaluate(self, device: Device, ctx: EvaluationContext) -> Issue | None:
        if not self.enabled:
            return None
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
