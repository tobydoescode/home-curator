from typing import Any

from home_curator.rules.base import (
    Device,
    Entity,
    EntitySummary,
    EvaluationContext,
    TargetKind,
)


def make_device(
    *,
    id: str = "d1",
    name: str = "n",
    name_by_user: str | None = None,
    manufacturer: str | None = None,
    model: str | None = None,
    area_id: str | None = None,
    area_name: str | None = None,
    integration: str | None = None,
    disabled_by: str | None = None,
    entities: list[EntitySummary] | None = None,
    created_at: str | None = None,
    modified_at: str | None = None,
    state: dict[str, Any] | None = None,
) -> Device:
    return Device(
        id=id,
        name=name,
        name_by_user=name_by_user,
        manufacturer=manufacturer,
        model=model,
        area_id=area_id,
        area_name=area_name,
        integration=integration,
        disabled_by=disabled_by,
        entities=entities or [],
        created_at=created_at,
        modified_at=modified_at,
        state=state or {},
    )


def make_entity(
    *,
    entity_id: str = "light.x",
    name: str | None = "x",
    original_name: str | None = None,
    icon: str | None = None,
    domain: str = "light",
    platform: str = "hue",
    device_id: str | None = None,
    area_id: str | None = None,
    area_name: str | None = None,
    disabled_by: str | None = None,
    hidden_by: str | None = None,
    unique_id: str | None = None,
    created_at: str | None = None,
    modified_at: str | None = None,
    state: dict[str, Any] | None = None,
) -> Entity:
    return Entity(
        entity_id=entity_id,
        name=name,
        original_name=original_name,
        icon=icon,
        domain=domain,
        platform=platform,
        device_id=device_id,
        area_id=area_id,
        area_name=area_name,
        disabled_by=disabled_by,
        hidden_by=hidden_by,
        unique_id=unique_id,
        created_at=created_at,
        modified_at=modified_at,
        state=state or {},
    )


def make_context(
    *,
    area_name_to_id: dict[str, str] | None = None,
    area_id_to_name: dict[str, str] | None = None,
    exceptions: set[tuple[TargetKind, str, str]] | None = None,
    exc: set[tuple[TargetKind, str, str]] | None = None,
    devices: list[Device] | None = None,
    devices_by_id: dict[str, Device] | None = None,
) -> EvaluationContext:
    return EvaluationContext(
        area_name_to_id=area_name_to_id or {},
        area_id_to_name=area_id_to_name or {},
        exceptions=exceptions if exceptions is not None else exc or set(),
        devices_by_id=devices_by_id if devices_by_id is not None else {
            d.id: d for d in devices or []
        },
    )
