import re
from dataclasses import dataclass, field
from re import Pattern

from home_curator.policies.schema import (
    NamingConventionPolicy,
    NamingPatternConfig,
    NamingPreset,
    RoomOverride,
)
from home_curator.rules.base import Device, EvaluationContext, Issue, Severity

PRESET_TO_PATTERN: dict[str, str] = {
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


def _room_prefix(preset: NamingPreset, area_id: str, area_name: str | None) -> str | None:
    """The expected prefix a device name must start with, derived from the active preset.

    Returns None if the preset cannot derive a prefix (e.g. custom — user's pattern
    owns prefixing explicitly).
    """
    if preset == "snake_case":
        return area_id.lower()
    if preset == "kebab-case":
        # Prefer area_name → lower + spaces-to-hyphens for readable prefixes;
        # fall back to area_id with underscores swapped for hyphens.
        if area_name:
            return area_name.lower().replace(" ", "-")
        return area_id.lower().replace("_", "-")
    if preset == "title-case":
        return area_name or ""
    if preset == "prefix-type-n":
        return area_id.lower()
    return None


@dataclass
class _OverrideEntry:
    enabled: bool
    pattern: Pattern[str] | None
    preset: NamingPreset | None
    starts_with_room: bool | None


@dataclass
class CompiledNamingConvention:
    id: str
    enabled: bool
    severity: Severity
    global_preset: NamingPreset
    global_pattern: Pattern[str]
    global_starts_with_room: bool
    overrides_by_area_id: dict[str, _OverrideEntry] = field(default_factory=dict)
    pending_room_overrides: list[tuple[str, _OverrideEntry]] = field(default_factory=list)
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
        if self.pending_room_overrides:
            still_pending: list[tuple[str, _OverrideEntry]] = []
            for room_name, entry in self.pending_room_overrides:
                resolved = ctx.resolve_area_id_from_name(room_name)
                if resolved is None:
                    still_pending.append((room_name, entry))
                else:
                    self.overrides_by_area_id[resolved] = entry
                    if room_name in self.unresolved_room_names:
                        self.unresolved_room_names.remove(room_name)
            self.pending_room_overrides = still_pending

        override = device.area_id and self.overrides_by_area_id.get(device.area_id)
        if override and not override.enabled:
            return None  # Room opts out.

        pattern = override.pattern if override and override.pattern else self.global_pattern
        preset = override.preset if override and override.preset else self.global_preset
        swr = (
            override.starts_with_room
            if override and override.starts_with_room is not None
            else self.global_starts_with_room
        )
        if not pattern.match(device.display_name):
            return Issue(
                policy_id=self.id, rule_type=self.rule_type, severity=self.severity,
                message="Name Doesn't Match Convention", device_id=device.id,
            )
        if swr and device.area_id:
            prefix = _room_prefix(preset, device.area_id, device.area_name)
            if prefix is not None and not device.display_name.startswith(prefix):
                return Issue(
                    policy_id=self.id, rule_type=self.rule_type, severity=self.severity,
                    message="Name Doesn't Start With Its Room", device_id=device.id,
                )
        return None


def compile_naming_convention(
    p: NamingConventionPolicy, ctx: EvaluationContext | None = None
) -> CompiledNamingConvention:
    overrides: dict[str, _OverrideEntry] = {}
    pending: list[tuple[str, _OverrideEntry]] = []
    unresolved: list[str] = []
    for override in p.rooms:
        entry = _OverrideEntry(
            enabled=override.enabled,
            pattern=(
                _pattern_from_config(NamingPatternConfig(
                    preset=override.preset, pattern=override.pattern,
                ))
                if override.enabled and override.preset is not None else None
            ),
            preset=override.preset if override.enabled else None,
            starts_with_room=override.starts_with_room,
        )
        area_id = _resolve_area_id(override, ctx)
        if area_id is None:
            room_name = override.room
            if room_name and ctx is None:
                pending.append((room_name, entry))
                unresolved.append(room_name)
            else:
                unresolved.append(room_name or "?")
            continue
        overrides[area_id] = entry
    return CompiledNamingConvention(
        id=p.id,
        enabled=p.enabled,
        severity=p.severity,
        global_preset=p.global_.preset,
        global_pattern=_pattern_from_config(p.global_),
        global_starts_with_room=p.starts_with_room,
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
