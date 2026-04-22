from dataclasses import dataclass

from home_curator.policies.schema import ReappearedAfterDeletePolicy
from home_curator.rules.base import Device, EvaluationContext, Issue, Severity


@dataclass
class CompiledReappeared:
    id: str
    enabled: bool
    severity: Severity
    rule_type: str = "reappeared_after_delete"
    compile_error: str | None = None

    def evaluate(self, device: Device, ctx: EvaluationContext) -> Issue | None:
        if not self.enabled:
            return None
        if (device.id, self.id) in ctx.exceptions:
            return None
        if device.state.get("reappeared_after_delete"):
            return Issue(
                policy_id=self.id,
                rule_type=self.rule_type,
                severity=self.severity,
                message="Device Reappeared After Being Deleted",
                device_id=device.id,
            )
        return None


def compile_reappeared(p: ReappearedAfterDeletePolicy) -> CompiledReappeared:
    return CompiledReappeared(id=p.id, enabled=p.enabled, severity=p.severity)
