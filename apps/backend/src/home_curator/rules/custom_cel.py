from dataclasses import dataclass, field
from typing import Any

import celpy

from home_curator.policies.schema import CustomPolicy
from home_curator.rules.base import Device, EvaluationContext, Issue, Severity


def _compile(expr: str):
    env = celpy.Environment()
    ast = env.compile(expr)
    program = env.program(ast)
    return program


@dataclass
class CompiledCustom:
    id: str
    enabled: bool
    severity: Severity
    message: str
    rule_type: str = "custom"
    _when: Any = None
    _assert: Any = None
    compile_error: str | None = None
    runtime_errors: int = field(default=0)

    def evaluate(self, device: Device, ctx: EvaluationContext) -> Issue | None:
        if not self.enabled or self.compile_error:
            return None
        if (device.id, self.id) in ctx.exceptions:
            return None
        cel_ctx = {"device": celpy.json_to_cel(device.to_cel_context())}
        try:
            if self._when is not None:
                applicable = bool(self._when.evaluate(cel_ctx))
                if not applicable:
                    return None
            asserted = bool(self._assert.evaluate(cel_ctx))
        except Exception:
            self.runtime_errors += 1
            return None
        if asserted:
            return None
        return Issue(
            policy_id=self.id,
            rule_type=self.rule_type,
            severity=self.severity,
            message=self.message,
            device_id=device.id,
        )


def compile_custom(p: CustomPolicy) -> CompiledCustom:
    rule = CompiledCustom(
        id=p.id,
        enabled=p.enabled,
        severity=p.severity,
        message=p.message,
    )
    try:
        if p.when_ and p.when_.strip() != "true":
            rule._when = _compile(p.when_)
        rule._assert = _compile(p.assert_)
    except Exception as e:  # celpy parse errors, etc.
        rule.compile_error = f"CEL compile error: {e}"
    return rule
