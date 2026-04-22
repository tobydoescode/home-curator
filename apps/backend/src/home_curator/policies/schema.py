from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Severity = Literal["info", "warning", "error"]
NamingPreset = Literal["snake_case", "kebab-case", "title-case", "prefix-type-n", "custom"]
CustomScope = Literal["devices"]


class _PolicyBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    enabled: bool = True
    severity: Severity


class MissingAreaPolicy(_PolicyBase):
    type: Literal["missing_area"]


class ReappearedAfterDeletePolicy(_PolicyBase):
    type: Literal["reappeared_after_delete"]


class NamingPatternConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: NamingPreset
    pattern: str | None = None

    @model_validator(mode="after")
    def _custom_needs_pattern(self):
        has_pattern = bool((self.pattern or "").strip())
        if self.preset == "custom" and not has_pattern:
            raise ValueError("preset='custom' requires a non-empty 'pattern'")
        if self.preset != "custom" and has_pattern:
            raise ValueError("'pattern' is only valid when preset='custom'")
        return self


class RoomOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room: str | None = None
    area_id: str | None = None
    enabled: bool = True
    preset: NamingPreset | None = None
    pattern: str | None = None
    starts_with_room: bool | None = None

    @model_validator(mode="after")
    def _needs_reference(self):
        if not self.room and not self.area_id:
            raise ValueError("room override needs 'room' or 'area_id'")
        return self

    @model_validator(mode="after")
    def _enabled_requires_preset(self):
        if self.enabled and self.preset is None:
            raise ValueError("enabled override must specify 'preset'")
        return self

    @model_validator(mode="after")
    def _pattern_valid_for_preset(self):
        if not self.enabled or self.preset is None:
            return self
        has_pattern = bool((self.pattern or "").strip())
        if self.preset == "custom" and not has_pattern:
            raise ValueError("preset='custom' requires a non-empty 'pattern'")
        if self.preset != "custom" and has_pattern:
            raise ValueError("'pattern' is only valid when preset='custom'")
        return self


class NamingConventionPolicy(_PolicyBase):
    type: Literal["naming_convention"]
    global_: NamingPatternConfig = Field(alias="global")
    starts_with_room: bool = False
    rooms: list[RoomOverride] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class CustomPolicy(_PolicyBase):
    type: Literal["custom"]
    scope: CustomScope
    when_: str = Field(alias="when", default="true")
    assert_: str = Field(alias="assert")
    message: str

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


Policy = Annotated[
    MissingAreaPolicy
    | ReappearedAfterDeletePolicy
    | NamingConventionPolicy
    | CustomPolicy,
    Field(discriminator="type"),
]


class PoliciesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    policies: list[Policy]
