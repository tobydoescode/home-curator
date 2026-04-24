"""Validated pydantic models for the Home Assistant client boundary.

Read models (HADevice, HAEntity, HAArea) use extra="ignore" so future
HA fields don't raise — we silently drop them until we add them here.
Patch models (HADeviceUpdate, HAEntityUpdate) use extra="forbid" because
caller typos would otherwise silently fail to update anything. Event
types form a discriminated union on the `kind` Literal field.
"""

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
