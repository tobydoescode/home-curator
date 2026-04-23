"""User-authored policy rule backed by the CEL expression language."""
from dataclasses import dataclass, field
from typing import Any, ClassVar

import celpy

from home_curator.policies.schema import CustomPolicy
from home_curator.rules.base import Device, EvaluationContext, Issue, Severity

_ENV = celpy.Environment()

# Cap on the per-rule runtime-error counter to prevent unbounded growth when a
# misconfigured expression fires against many devices. The engine exposes the
# counter as a diagnostic signal; the exact value is not load-bearing.
MAX_RUNTIME_ERRORS = 1000


def _compile(expr: str):
    ast = _ENV.compile(expr)
    return _ENV.program(ast)


@dataclass
class CompiledCustom:
    # Public, required at construction:
    id: str
    enabled: bool
    severity: Severity
    message: str

    # Class-level identifier, not per-instance data:
    rule_type: ClassVar[str] = "custom"

    # Populated by `compile_custom`; not part of the public constructor.
    _when: Any = field(default=None, init=False, repr=False)
    _assert: Any = field(default=None, init=False, repr=False)
    compile_error: str | None = field(default=None, init=False)
    runtime_errors: int = field(default=0, init=False)

    def evaluate(self, device: Device, ctx: EvaluationContext) -> Issue | None:
        if not self.enabled or self.compile_error:
            return None
        if ("device", device.id, self.id) in ctx.exceptions:
            return None
        cel_ctx = {"device": celpy.json_to_cel(device.to_cel_context())}
        try:
            if self._when is not None:
                if not bool(self._when.evaluate(cel_ctx)):
                    return None
            asserted = bool(self._assert.evaluate(cel_ctx))
        except Exception:
            # cel-python raises CELEvalError on bad field access etc. Broad
            # catch prevents one bad device from breaking the whole evaluation
            # pass; counter caps so the number stays useful for diagnostics.
            if self.runtime_errors < MAX_RUNTIME_ERRORS:
                self.runtime_errors += 1
            return None
        if asserted:
            return None
        return Issue(
            policy_id=self.id,
            rule_type=self.rule_type,
            severity=self.severity,
            message=self.message,
            target_kind="device",
            target_id=device.id,
        )


def compile_custom(p: CustomPolicy) -> CompiledCustom:
    rule = CompiledCustom(
        id=p.id,
        enabled=p.enabled,
        severity=p.severity,
        message=p.message,
    )
    try:
        # Skip compiling the default "true" literal — it always gates on, so
        # the evaluate-time None-check treats absence as "always applicable".
        if p.when_ and p.when_.strip() != "true":
            rule._when = _compile(p.when_)
        rule._assert = _compile(p.assert_)
    except Exception as e:
        # celpy surfaces parse errors via its own exception hierarchy; we
        # catch broadly so a malformed rule doesn't crash the whole engine.
        rule.compile_error = f"CEL compile error: {e}"
    return rule
