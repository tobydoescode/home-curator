from dataclasses import dataclass

from home_curator.policies.schema import (
    CustomPolicy,
    MissingAreaPolicy,
    NamingConventionPolicy,
    PoliciesFile,
    ReappearedAfterDeletePolicy,
)
from home_curator.rules.base import (
    CompiledPolicy, Device, Entity, EvaluationContext, Issue,
)
from home_curator.rules.custom_cel import compile_custom
from home_curator.rules.missing_area import compile_missing_area
from home_curator.rules.naming_convention import compile_naming_convention
from home_curator.rules.reappeared_after_delete import compile_reappeared


@dataclass
class RuleEngine:
    compiled: list[CompiledPolicy]

    @classmethod
    def compile(cls, file_: PoliciesFile, ctx: EvaluationContext) -> "RuleEngine":
        rules: list[CompiledPolicy] = []
        for p in file_.policies:
            if isinstance(p, MissingAreaPolicy):
                rules.append(compile_missing_area(p))
            elif isinstance(p, NamingConventionPolicy):
                rules.append(compile_naming_convention(p, ctx))
            elif isinstance(p, ReappearedAfterDeletePolicy):
                rules.append(compile_reappeared(p))
            elif isinstance(p, CustomPolicy):
                rules.append(compile_custom(p))
            else:
                raise TypeError(f"Unhandled policy type: {type(p).__name__}")
        return cls(compiled=rules)

    def evaluate(self, thing: Device | Entity, ctx: EvaluationContext) -> list[Issue]:
        """Dispatch by thing type. Rules whose scope doesn't match the
        current scope are skipped silently — they aren't errors, they
        just don't apply. Compile-errored rules are always skipped."""
        scope = "entities" if isinstance(thing, Entity) else "devices"
        out: list[Issue] = []
        for r in self.compiled:
            if r.compile_error:
                continue
            if r.scope != scope:
                continue
            issue = r.evaluate(thing, ctx)
            if issue is not None:
                out.append(issue)
        return out

    def compile_errors(self) -> dict[str, str]:
        return {
            r.id: r.compile_error
            for r in self.compiled
            if r.compile_error is not None
        }
