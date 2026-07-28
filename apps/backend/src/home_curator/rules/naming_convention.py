import re
from dataclasses import dataclass, field

from home_curator.policies.schema import (
    NamingConventionPolicy,
    NamingPatternConfig,
    NamingPreset,
    RoomOverride,
)
from home_curator.rules.base import (
    Device,
    EvaluationContext,
    Issue,
    Severity,
    TargetScope,
)
from home_curator.user_regex import UserPattern, compile_user_pattern

PRESET_TO_PATTERN: dict[str, str] = {
    "snake_case": r"^[a-z0-9]+(_[a-z0-9]+)*$",
    "kebab-case": r"^[a-z0-9]+(-[a-z0-9]+)*$",
    # Title Case tolerates real-world English device naming:
    #   - apostrophes inside or trailing a word ("Clara's", "Wills'")
    #   - hyphenated words where each segment is capitalised ("En-Suite")
    #   - acronyms and initialisms ("AP", "ESPresense") via [A-Z]+[a-z0-9']*
    #   - standalone digit-words after the first token ("Side Lamp 2") —
    #     the first token must still start with a letter so names don't
    #     begin with a number.
    #   - digit-led techy abbreviations after the first token ("Printer 3D",
    #     "Camera 4K", "Sensor 12V") via [0-9]+[A-Z]+[a-z0-9']*. Note "after":
    #     "3D Printer" is rejected, because the first token must start with a
    #     letter. The examples here previously said otherwise.
    #   - lowercase function words (articles, short prepositions, conjunctions)
    #     after the first token ("Mum and Dad's Bedroom", "Rooms of the House").
    #     Never at the start — that's a real capitalisation mistake.
    #   - a trailing parenthesised annotation ("(Local)") with letters / digits
    #     / spaces / hyphens / apostrophes — colons are deliberately excluded
    #     so MAC addresses ("(CC:8D:A2:50:E6:7E)") stay flagged.
    # Snake / kebab stay strict — those are machine-facing formats.
    "title-case": (
        r"^[A-Z]+[a-z0-9']*(-[A-Z]+[a-z0-9']*)*"
        r"(\s([A-Z]+[a-z0-9']*|[0-9]+[A-Z]+[a-z0-9']*|[0-9]+|"
        r"(?:and|but|for|the|via|an|as|at|by|if|in|of|on|or|to|vs|a))"
        r"(-[A-Z]+[a-z0-9']*)*)*"
        r"(\s\([A-Za-z0-9 '\-]+\))?$"
    ),
    "prefix-type-n": r"^[a-z]+_[a-z]+_[0-9]+$",
}


def _pattern_from_config(cfg: NamingPatternConfig) -> UserPattern:
    if cfg.preset == "custom":
        if not cfg.pattern:
            raise ValueError("preset='custom' requires a non-empty pattern")
        return compile_user_pattern(cfg.pattern)
    # Built-in presets go through the same engine, so a preset and a custom
    # pattern cannot behave differently.
    return compile_user_pattern(PRESET_TO_PATTERN[cfg.preset])


def _room_prefix(preset: NamingPreset, area_id: str, area_name: str | None) -> str | None:
    """The expected prefix a device name must start with, derived from the active preset.

    Returns None if the preset cannot derive a prefix (e.g. custom — user's pattern
    owns prefixing explicitly).
    """
    if preset == "snake_case":
        # Lower + space-to-underscore, then drop any character that isn't a
        # valid snake_case token character, then collapse consecutive
        # underscores. Handles apostrophes ("Clara's Bedroom" →
        # "claras_bedroom"), hyphens ("En-Suite" → "ensuite"), and
        # punctuation that leaves adjacent separators ("Mum & Dad's
        # Bedroom" → "mum_dads_bedroom", not "mum__dads_bedroom"). Without
        # the collapse the prefix itself would be invalid snake_case and
        # every device in a punctuated-name room would fail the
        # starts-with-room check.
        source = (
            area_name.lower().replace(" ", "_")
            if area_name
            else area_id.lower().replace("-", "_")
        )
        return re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]", "", source))
    if preset == "kebab-case":
        # Prefer area_name → lower + spaces-to-hyphens for readable prefixes;
        # fall back to area_id with underscores swapped for hyphens.
        if area_name:
            return area_name.lower().replace(" ", "-")
        return area_id.lower().replace("_", "-")
    if preset == "title-case":
        return area_name
    if preset == "prefix-type-n":
        return area_id.lower()
    return None


@dataclass
class _OverrideEntry:
    enabled: bool
    pattern: UserPattern | None
    preset: NamingPreset | None
    starts_with_room: bool | None


@dataclass
class CompiledNamingConvention:
    id: str
    enabled: bool
    severity: Severity
    global_preset: NamingPreset
    global_pattern: UserPattern
    global_starts_with_room: bool
    overrides_by_area_id: dict[str, _OverrideEntry] = field(default_factory=dict)
    unresolved_room_names: list[str] = field(default_factory=list)
    rule_type: str = "naming_convention"
    scope: TargetScope = "devices"

    @property
    def compile_error(self) -> str | None:
        if self.unresolved_room_names:
            return f"unresolved rooms: {', '.join(self.unresolved_room_names)}"
        return None

    def evaluate(self, thing: object, ctx: EvaluationContext) -> Issue | None:
        if not self.enabled:
            return None
        assert isinstance(thing, Device)
        device = thing
        if ("device", device.id, self.id) in ctx.exceptions:
            return None

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
                message="Name Doesn't Match Convention",
                target_kind="device", target_id=device.id,
            )
        if swr and device.area_id:
            prefix = _room_prefix(preset, device.area_id, device.area_name)
            if prefix is not None and not device.display_name.startswith(prefix):
                return Issue(
                    policy_id=self.id, rule_type=self.rule_type, severity=self.severity,
                    message="Name Doesn't Start With Its Room",
                    target_kind="device", target_id=device.id,
                )
        return None


def compile_naming_convention(
    p: NamingConventionPolicy, ctx: EvaluationContext
) -> CompiledNamingConvention:
    """Resolve every room override against `ctx` up front.

    `ctx` is required rather than optional. It used to be allowed to be None,
    in which case unresolved overrides were stashed and promoted lazily on the
    first `evaluate()` that could resolve them — which made evaluation mutate
    the compiled rule. `RuleEngine.compile` has always supplied a ctx, so that
    path was unreachable in production, but it left `evaluate()` looking
    impure and would have become a genuine cross-thread race the moment
    anything compiled without one: evaluation runs concurrently in FastAPI's
    threadpool.
    """
    overrides: dict[str, _OverrideEntry] = {}
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
            unresolved.append(override.room or "?")
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
        unresolved_room_names=unresolved,
    )


def _resolve_area_id(override: RoomOverride, ctx: EvaluationContext) -> str | None:
    if override.area_id:
        return override.area_id
    if override.room:
        return ctx.resolve_area_id_from_name(override.room)
    return None


# Public re-exports so entity_naming (and any other future rule) can share
# the preset-to-pattern mapping and the room-prefix derivation without
# depending on private names.
pattern_from_config = _pattern_from_config
room_prefix = _room_prefix
