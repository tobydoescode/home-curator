import re
from dataclasses import dataclass, field
from re import Pattern

from home_curator.policies.schema import NamingConventionPolicy, NamingPatternConfig, RoomOverride
from home_curator.rules.base import Device, EvaluationContext, Issue, Severity

PRESET_TO_PATTERN = {
    "snake_case": r"^[a-z0-9]+(_[a-z0-9]+)*$",
    "kebab-case": r"^[a-z0-9]+(-[a-z0-9]+)*$",
    "title-case": r"^([A-Z][a-z0-9]+)(\s[A-Z][a-z0-9]+)*$",
    "prefix-type-n": r"^[a-z]+_[a-z]+_[0-9]+$",
}


def _pattern_from_config(cfg: NamingPatternConfig) -> Pattern[str]:
    if cfg.preset == "custom":
        if not cfg.pattern:
            raise ValueError("preset='custom' requires a non-empty pattern")
        return re.compile(cfg.pattern)
    return re.compile(PRESET_TO_PATTERN[cfg.preset])


@dataclass
class CompiledNamingConvention:
    id: str
    enabled: bool
    severity: Severity
    global_pattern: Pattern[str]
    overrides_by_area_id: dict[str, Pattern[str]] = field(default_factory=dict)
    # Room-name overrides that couldn't be resolved at compile time (no ctx).
    # Stored so evaluate() can attempt late resolution via the evaluation ctx.
    pending_room_overrides: list[tuple[str, Pattern[str]]] = field(default_factory=list)
    unresolved_room_names: list[str] = field(default_factory=list)
    rule_type: str = "naming_convention"

    @property
    def compile_error(self) -> str | None:
        if self.unresolved_room_names:
            return f"unresolved rooms: {', '.join(self.unresolved_room_names)}"
        return None

    def evaluate(self, device: Device, ctx: EvaluationContext) -> Issue | None:
        if not self.enabled:
            return None
        if (device.id, self.id) in ctx.exceptions:
            return None
        # Promote any pending room-name overrides that now resolve under the given
        # ctx, so subsequent evaluations use the fast dict path and compile_error
        # no longer reports resolved names.
        if self.pending_room_overrides:
            still_pending: list[tuple[str, Pattern[str]]] = []
            for room_name, room_pattern in self.pending_room_overrides:
                resolved = ctx.resolve_area_id_from_name(room_name)
                if resolved is None:
                    still_pending.append((room_name, room_pattern))
                else:
                    self.overrides_by_area_id[resolved] = room_pattern
                    if room_name in self.unresolved_room_names:
                        self.unresolved_room_names.remove(room_name)
            self.pending_room_overrides = still_pending

        pattern = self.global_pattern
        if device.area_id and device.area_id in self.overrides_by_area_id:
            pattern = self.overrides_by_area_id[device.area_id]
        if pattern.match(device.name):
            return None
        return Issue(
            policy_id=self.id,
            rule_type=self.rule_type,
            severity=self.severity,
            message="Name Doesn't Match Convention",
            device_id=device.id,
        )


def compile_naming_convention(
    p: NamingConventionPolicy, ctx: EvaluationContext | None = None
) -> CompiledNamingConvention:
    overrides: dict[str, re.Pattern[str]] = {}
    pending: list[tuple[str, re.Pattern[str]]] = []
    unresolved: list[str] = []
    for override in p.rooms:
        area_id = _resolve_area_id(override, ctx)
        if area_id is None:
            room_name = override.room
            if room_name and ctx is None:
                # No ctx at compile time — defer resolution to evaluate(), but
                # also mark as unresolved so compile_error reflects the situation.
                pending.append((room_name, _pattern_from_config(override)))
                unresolved.append(room_name)
            else:
                # ctx was present but room name still didn't resolve → truly unresolved.
                unresolved.append(room_name or "?")
            continue
        overrides[area_id] = _pattern_from_config(override)
    return CompiledNamingConvention(
        id=p.id,
        enabled=p.enabled,
        severity=p.severity,
        global_pattern=_pattern_from_config(p.global_),
        overrides_by_area_id=overrides,
        pending_room_overrides=pending,
        unresolved_room_names=unresolved,
    )


def _resolve_area_id(override: RoomOverride, ctx: EvaluationContext | None) -> str | None:
    if override.area_id:
        return override.area_id
    if override.room and ctx:
        return ctx.resolve_area_id_from_name(override.room)
    return None
