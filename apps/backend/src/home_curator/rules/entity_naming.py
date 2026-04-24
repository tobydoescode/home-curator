"""Entity naming-convention rule: two independent checks per entity.

Block `name` mirrors the device `naming_convention` rule verbatim (preset,
pattern, starts_with_room, per-room overrides). Block `entity_id` is a
locked-snake_case variant — rooms may opt out, but can't pick a different
preset. Both blocks fire independently; evaluate() returns the first issue
(protocol conformance), evaluate_all() returns every failing block.

Starts-with semantics for owned entities anchor on the owning DEVICE's
name (not the room). The room prefix flows transitively through the
device's own naming rule: `entity name → device name → room`. When the
device's name doesn't itself start with the room, the entity-level issue
is suppressed — the device rule will surface the problem once, instead of
N times (once per child entity).

Standalone entities (no owning device) fall back to checking the room
prefix directly — they have no other anchor.
"""
import re
from dataclasses import dataclass, field
from re import Pattern

from home_curator.policies.schema import (
    EntityIdBlock,
    EntityNameBlock,
    EntityNamingConventionPolicy,
    NamingPatternConfig,
    NamingPreset,
)
from home_curator.rules.base import (
    Entity,
    EvaluationContext,
    Issue,
    Severity,
    TargetScope,
)
from home_curator.rules.naming_convention import (
    _OverrideEntry,
    pattern_from_config,
    room_prefix,
)

# entity_id is "<domain>.<object>"; both domain (always snake by HA) and
# object are checked against snake_case. Object is what a per-room prefix
# applies to.
_ENTITY_ID_OBJECT_PATTERN: Pattern[str] = pattern_from_config(
    NamingPatternConfig(preset="snake_case"),
)


def _to_snake(s: str) -> str:
    """Snake-case a human string the same way `_room_prefix` does for
    snake_case presets — lowercase, spaces→underscores, strip everything
    except [a-z0-9_], collapse runs of underscores. Used to compare an
    entity_id's object part against its owning device's snaked name."""
    source = s.lower().replace(" ", "_")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]", "", source))


@dataclass
class _NameCompiled:
    global_preset: NamingPreset
    global_pattern: Pattern[str]
    global_starts_with_room: bool
    overrides_by_area_id: dict[str, _OverrideEntry] = field(default_factory=dict)


@dataclass
class _EntityIdCompiled:
    global_starts_with_room: bool
    # area_id → enabled? (opt-out only, no preset/pattern).
    overrides_by_area_id: dict[str, bool] = field(default_factory=dict)


@dataclass
class CompiledEntityNaming:
    id: str
    enabled: bool
    severity: Severity
    name_cfg: _NameCompiled
    entity_id_cfg: _EntityIdCompiled
    rule_type: str = "entity_naming_convention"
    scope: TargetScope = "entities"
    compile_error: str | None = None

    def evaluate(self, thing: object, ctx: EvaluationContext) -> Issue | None:
        """Protocol-compliant evaluator. Returns the first failing block
        (Entity ID first, then Name). Callers that need both must call
        evaluate_all()."""
        assert isinstance(thing, Entity)
        issues = self.evaluate_all(thing, ctx)
        return issues[0] if issues else None

    def evaluate_all(self, entity: Entity, ctx: EvaluationContext) -> list[Issue]:
        if not self.enabled:
            return []
        if ("entity", entity.entity_id, self.id) in ctx.exceptions:
            return []

        out: list[Issue] = []

        # ---- entity_id block ----
        eid_opted_out = (
            entity.area_id is not None
            and entity.area_id in self.entity_id_cfg.overrides_by_area_id
            and self.entity_id_cfg.overrides_by_area_id[entity.area_id] is False
        )
        device = (
            ctx.devices_by_id.get(entity.device_id) if entity.device_id else None
        )

        if not eid_opted_out:
            # entity_id is "<domain>.<object>". Domain part is always snake
            # in HA; we assert the object part (what the user controls via
            # unique_id / rename) against snake_case + optional room prefix.
            try:
                _, object_id = entity.entity_id.split(".", 1)
            except ValueError:
                object_id = entity.entity_id  # malformed; will fail the pattern

            if not _ENTITY_ID_OBJECT_PATTERN.match(object_id):
                out.append(self._issue(entity, "Entity ID Doesn't Match Convention"))
            elif self.entity_id_cfg.global_starts_with_room and entity.area_id:
                area_name = ctx.area_id_to_name.get(entity.area_id)
                snake_room_prefix = room_prefix(
                    "snake_case", entity.area_id, area_name,
                )
                if device is not None:
                    # Owned: anchor is the snake-cased device display name,
                    # not the room directly. Room flows transitively.
                    snake_device = _to_snake(device.display_name)
                    if object_id.startswith(snake_device):
                        pass  # inherited or user-extended — OK
                    elif (
                        snake_room_prefix
                        and not snake_device.startswith(snake_room_prefix)
                    ):
                        # Device itself doesn't start with room — device rule
                        # will fire; suppress entity-level complaint to avoid
                        # duplicate noise.
                        pass
                    else:
                        out.append(self._issue(
                            entity, "Entity ID Doesn't Start With Device",
                        ))
                else:
                    # Standalone: room is the only anchor.
                    if (
                        snake_room_prefix
                        and not object_id.startswith(snake_room_prefix)
                    ):
                        out.append(self._issue(
                            entity, "Entity ID Doesn't Start With Its Room",
                        ))

        # ---- name block ----
        # Entity inherits its friendly name from the owning device when it
        # has neither `name` nor `original_name` — there's nothing
        # entity-authored to judge. The device's own naming rule already
        # covers both the preset and the prefix for the device's name, so
        # skip the entity-level name block entirely.
        if (
            entity.name is None
            and entity.original_name is None
            and device is not None
        ):
            return out
        override = (
            self.name_cfg.overrides_by_area_id.get(entity.area_id)
            if entity.area_id else None
        )
        if override and not override.enabled:
            return out  # this room opts out of the name check
        pattern = (
            override.pattern if override and override.pattern
            else self.name_cfg.global_pattern
        )
        preset = (
            override.preset if override and override.preset
            else self.name_cfg.global_preset
        )
        swr = (
            override.starts_with_room
            if override and override.starts_with_room is not None
            else self.name_cfg.global_starts_with_room
        )
        display = entity.name or entity.original_name or entity.entity_id
        if not pattern.match(display):
            out.append(self._issue(entity, "Name Doesn't Match Convention"))
        elif swr and entity.area_id:
            area_name = ctx.area_id_to_name.get(entity.area_id)
            room_pref = room_prefix(preset, entity.area_id, area_name)
            # Inherited-from-device: entity has no own name, so display IS
            # the device name. Device rule handles the prefix; skip.
            inherited = entity.name is None and entity.original_name is None
            if inherited:
                return out
            if device is not None:
                anchor = device.display_name
                if display.startswith(anchor):
                    pass  # extended device name — OK
                elif area_name and not anchor.lower().startswith(area_name.lower()):
                    # Device name itself doesn't start with the room's
                    # display name — device rule will fire; dedupe.
                    pass
                else:
                    out.append(self._issue(
                        entity, "Name Doesn't Start With Device",
                    ))
            else:
                # Standalone: room is the only anchor.
                if room_pref and not display.startswith(room_pref):
                    out.append(self._issue(
                        entity, "Name Doesn't Start With Its Room",
                    ))

        return out

    def _issue(self, entity: Entity, message: str) -> Issue:
        return Issue(
            policy_id=self.id, rule_type=self.rule_type, severity=self.severity,
            message=message,
            target_kind="entity", target_id=entity.entity_id,
        )


def compile_entity_naming(
    p: EntityNamingConventionPolicy, ctx: EvaluationContext | None = None,
) -> CompiledEntityNaming:
    name_cfg = _compile_name_block(p.name, ctx)
    eid_cfg = _compile_entity_id_block(p.entity_id, ctx)
    return CompiledEntityNaming(
        id=p.id, enabled=p.enabled, severity=p.severity,
        name_cfg=name_cfg, entity_id_cfg=eid_cfg,
    )


def _compile_name_block(
    block: EntityNameBlock, ctx: EvaluationContext | None,
) -> _NameCompiled:
    overrides: dict[str, _OverrideEntry] = {}
    for o in block.rooms:
        area_id = _resolve_area_id(o.area_id, o.room, ctx)
        if area_id is None:
            continue
        overrides[area_id] = _OverrideEntry(
            enabled=o.enabled,
            pattern=(
                pattern_from_config(NamingPatternConfig(
                    preset=o.preset, pattern=o.pattern,
                )) if o.enabled and o.preset else None
            ),
            preset=o.preset if o.enabled else None,
            starts_with_room=o.starts_with_room,
        )
    return _NameCompiled(
        global_preset=block.global_.preset,
        global_pattern=pattern_from_config(block.global_),
        global_starts_with_room=block.starts_with_room,
        overrides_by_area_id=overrides,
    )


def _compile_entity_id_block(
    block: EntityIdBlock, ctx: EvaluationContext | None,
) -> _EntityIdCompiled:
    overrides: dict[str, bool] = {}
    for o in block.rooms:
        area_id = _resolve_area_id(o.area_id, o.room, ctx)
        if area_id is None:
            continue
        overrides[area_id] = o.enabled
    return _EntityIdCompiled(
        global_starts_with_room=block.starts_with_room,
        overrides_by_area_id=overrides,
    )


def _resolve_area_id(
    area_id: str | None, room: str | None, ctx: EvaluationContext | None,
) -> str | None:
    if area_id:
        return area_id
    if room and ctx:
        return ctx.resolve_area_id_from_name(room)
    return None
