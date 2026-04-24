"""Validated pydantic models for the Home Assistant client boundary.

Read models (HADevice, HAEntity, HAArea) use extra="ignore" so future
HA fields don't raise — we silently drop them until we add them here.
Patch models (HADeviceUpdate, HAEntityUpdate) use extra="forbid" because
caller typos would otherwise silently fail to update anything. Event
types form a discriminated union on the `kind` Literal field.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class HAArea(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    id: str
    name: str


class HADeviceEntityRef(BaseModel):
    """Lightweight entity reference carried on HADevice.entities."""
    model_config = ConfigDict(frozen=True, extra="ignore")
    id: str
    domain: str


class HADevice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    id: str
    name: str | None = None
    name_by_user: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    area_id: str | None = None
    integration: str | None = None
    disabled_by: str | None = None
    identifiers: list[list[str]] = Field(default_factory=list)
    config_entries: list[str] = Field(default_factory=list)
    entities: list[HADeviceEntityRef] = Field(default_factory=list)
    created_at: str | None = None
    modified_at: str | None = None


class HAEntity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    entity_id: str
    name: str | None = None
    original_name: str | None = None
    icon: str | None = None
    platform: str = ""
    device_id: str | None = None
    area_id: str | None = None
    disabled_by: str | None = None
    hidden_by: str | None = None
    unique_id: str | None = None
    created_at: str | None = None
    modified_at: str | None = None


class HADeviceUpdate(BaseModel):
    """Partial device update. Only explicitly-set fields are sent to HA via
    `model_dump(exclude_unset=True)`. `None` means "clear the field"."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    area_id: str | None = None
    name_by_user: str | None = None


class HAEntityUpdate(BaseModel):
    """Partial entity update. Only explicitly-set fields are sent to HA via
    `model_dump(exclude_unset=True)`. `None` means "clear the field".
    `new_entity_id` renames the HA entity slug."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    new_entity_id: str | None = None
    name: str | None = None
    area_id: str | None = None
    disabled_by: str | None = None
    hidden_by: str | None = None
    icon: str | None = None


class _EventBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class ReconnectedEvent(_EventBase):
    kind: Literal["reconnected"] = "reconnected"


class DeviceUpdatedEvent(_EventBase):
    kind: Literal["device_updated"] = "device_updated"
    # HA may emit device_registry_updated without a device_id (broad registry
    # change); None means "refresh all devices".
    device_id: str | None = None


class AreaUpdatedEvent(_EventBase):
    kind: Literal["area_updated"] = "area_updated"


class EntityUpdatedEvent(_EventBase):
    kind: Literal["entity_updated"] = "entity_updated"
    # HA may emit entity_registry_updated without an entity_id (broad
    # registry change); None means "refresh the entity cache broadly".
    entity_id: str | None = None


class EntityDeletedEvent(_EventBase):
    kind: Literal["entity_deleted"] = "entity_deleted"
    # Same rationale as EntityUpdatedEvent.entity_id — preserve broad
    # refresh behavior when HA omits the id.
    entity_id: str | None = None


HAEvent = Annotated[
    ReconnectedEvent
    | DeviceUpdatedEvent
    | AreaUpdatedEvent
    | EntityUpdatedEvent
    | EntityDeletedEvent,
    Field(discriminator="kind"),
]
