from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Severity = Literal["info", "warning", "error"]
NamingPreset = Literal["snake_case", "kebab-case", "title-case", "prefix-type-n", "custom"]


class _PolicyBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
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
        if self.preset == "custom" and not self.pattern:
            raise ValueError("preset='custom' requires a 'pattern'")
        if self.preset != "custom" and self.pattern:
            raise ValueError("'pattern' is only valid when preset='custom'")
        return self


class RoomOverride(NamingPatternConfig):
    room: str | None = None
    area_id: str | None = None

    @model_validator(mode="after")
    def _needs_reference(self):
        if not self.room and not self.area_id:
            raise ValueError("room override needs 'room' or 'area_id'")
        return self


class NamingConventionPolicy(_PolicyBase):
    type: Literal["naming_convention"]
    global_: NamingPatternConfig = Field(alias="global")
    rooms: list[RoomOverride] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class CustomPolicy(_PolicyBase):
    type: Literal["custom"]
    when_: str = Field(alias="when", default="true")
    assert_: str = Field(alias="assert")
    message: str

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


Policy = Annotated[
    MissingAreaPolicy | ReappearedAfterDeletePolicy | NamingConventionPolicy | CustomPolicy,
    Field(discriminator="type"),
]


class PoliciesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    policies: list[Policy]
