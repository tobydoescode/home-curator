"""User-authored policy rule backed by the CEL expression language."""
from dataclasses import dataclass, field
from typing import Any

import celpy
from celpy.adapter import json_to_cel

from home_curator.policies.schema import CustomPolicy
from home_curator.rules.base import (
    Device,
    Entity,
    EvaluationContext,
    Issue,
    Severity,
    TargetKind,
    TargetScope,
)

_ENV = celpy.Environment()

def _compile(expr: str) -> Any:
    ast = _ENV.compile(expr)
    return _ENV.program(ast)


@dataclass(frozen=True)
class CelOutcome:
    """What the expressions said about one device or entity.

    `matched_when` is False when the rule's `when` gate excluded this thing
    entirely. `passed` is the value of `assert` and is None when evaluation
    raised. The simulator reports all three separately, which is why this is
    richer than the bool `evaluate` needs.
    """

    matched_when: bool
    passed: bool | None
    error: str | None = None


@dataclass
class CompiledCustom:
    # Public, required at construction:
    id: str
    enabled: bool
    severity: Severity
    message: str

    rule_type: str = "custom"

    # "devices" by default; compile_custom sets "entities" from policy.scope.
    scope: TargetScope = field(default="devices")

    # Populated by `compile_custom`; not part of the public constructor.
    _when: Any = field(default=None, init=False, repr=False)
    _assert: Any = field(default=None, init=False, repr=False)
    compile_error: str | None = field(default=None, init=False)

    def check(self, thing: object, ctx: EvaluationContext) -> CelOutcome:
        """Run the expressions against `thing`. No policy semantics applied.

        Deliberately knows nothing about `enabled` or acknowledged
        exceptions — those are `evaluate`'s business, and the simulator wants
        the raw result. Sharing this is what stops the simulator and the rule
        engine drifting apart: they previously had two copies of this loop,
        with the simulator reaching into `_when` and `_assert` directly.
        """
        cel_ctx = self._cel_context(thing, ctx)
        try:
            if self._when is not None and not bool(self._when.evaluate(cel_ctx)):
                return CelOutcome(matched_when=False, passed=None)
            return CelOutcome(
                matched_when=True, passed=bool(self._assert.evaluate(cel_ctx))
            )
        except Exception as e:  # noqa: BLE001 - reported, not raised
            # cel-python raises CELEvalError on bad field access etc. A broad
            # catch stops one bad input breaking the whole evaluation pass.
            return CelOutcome(matched_when=True, passed=None, error=str(e))

    def _cel_context(
        self, thing: object, ctx: EvaluationContext
    ) -> dict[str, Any]:
        if self.scope == "entities":
            assert isinstance(thing, Entity)
            owning_device_ctx: dict[str, Any] | None = None
            if thing.device_id and thing.device_id in ctx.devices_by_id:
                owning_device_ctx = ctx.devices_by_id[thing.device_id].to_cel_context()
            area_name = (
                ctx.area_id_to_name.get(thing.area_id) if thing.area_id else None
            )
            return {
                "entity": json_to_cel(
                    thing.to_cel_context(
                        device_context=owning_device_ctx, area_name=area_name
                    )
                )
            }
        assert isinstance(thing, Device)
        return {"device": json_to_cel(thing.to_cel_context())}

    def evaluate(self, thing: object, ctx: EvaluationContext) -> Issue | None:
        if not self.enabled or self.compile_error:
            return None

        if self.scope == "entities":
            assert isinstance(thing, Entity)
            if ("entity", thing.entity_id, self.id) in ctx.exceptions:
                return None
            target_kind: TargetKind = "entity"
            target_id = thing.entity_id
        else:
            assert isinstance(thing, Device)
            if ("device", thing.id, self.id) in ctx.exceptions:
                return None
            target_kind = "device"
            target_id = thing.id

        outcome = self.check(thing, ctx)
        # An expression that threw reports nothing rather than failing the
        # whole pass; a rule that passed has no issue to report.
        if not outcome.matched_when or outcome.passed is not False:
            return None
        return Issue(
            policy_id=self.id,
            rule_type=self.rule_type,
            severity=self.severity,
            message=self.message,
            target_kind=target_kind,
            target_id=target_id,
        )


def compile_custom(p: CustomPolicy) -> CompiledCustom:
    rule = CompiledCustom(
        id=p.id,
        enabled=p.enabled,
        severity=p.severity,
        message=p.message,
        scope=p.scope,
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
