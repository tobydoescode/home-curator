"""Pydantic response models — the API's machine-readable contract.

These define the shapes returned by every endpoint. Paired with FastAPI's
`response_model=` they drive the OpenAPI spec at `/openapi.json`, which the
frontend uses to generate a typed client.
"""
from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["info", "warning", "error"]


class HealthResponse(BaseModel):
    ok: bool


class EntitySummary(BaseModel):
    """An entity owned by a device."""

    id: str
    domain: str


class IssueOut(BaseModel):
    """A single policy violation on a device."""

    policy_id: str
    rule_type: str
    severity: Severity
    message: str


class DeviceOut(BaseModel):
    """A device with its evaluated issues."""

    id: str
    name: str
    manufacturer: str | None = None
    model: str | None = None
    area_id: str | None = None
    area_name: str | None = None
    integration: str | None = None
    disabled_by: str | None = None
    entities: list[EntitySummary] = Field(default_factory=list)
    issue_count: int
    highest_severity: Severity | None = None
    issues: list[IssueOut] = Field(default_factory=list)


class AreaOut(BaseModel):
    """A Home Assistant area (room)."""

    id: str
    name: str


class DevicesListResponse(BaseModel):
    """Paginated device list with aggregate issue counts.

    `all_areas` and `all_issue_types` enumerate the full universe of filter
    options (not just what's in the current filtered result), so UI dropdowns
    stay populated with every option regardless of active filters.
    """

    devices: list[DeviceOut]
    total: int
    page: int
    page_size: int
    # Issue counts across the filtered result, keyed by rule_type.
    issue_counts_by_type: dict[str, int]
    # Device counts across the filtered result, keyed by area_name.
    # Areas with zero matches in the current filter appear here as 0.
    area_counts: dict[str, int] = Field(default_factory=dict)
    all_areas: list[AreaOut] = Field(default_factory=list)
    all_issue_types: list[str] = Field(default_factory=list)


class ExceptionOut(BaseModel):
    """An acknowledged policy exception for a device."""

    device_id: str
    policy_id: str
    acknowledged_at: str  # ISO-8601
    acknowledged_by: str | None = None
    note: str | None = None


class AcknowledgeResponse(BaseModel):
    ok: bool


class AssignRoomResult(BaseModel):
    device_id: str
    ok: bool
    error: str | None = None


class AssignRoomResponse(BaseModel):
    results: list[AssignRoomResult]


class RenameResponse(BaseModel):
    ok: bool


class RenamePatternResult(BaseModel):
    device_id: str
    matched: bool
    new_name: str | None = None
    ok: bool | None = None
    dry_run: bool | None = None
    reason: str | None = None
    error: str | None = None


class RenamePatternResponse(BaseModel):
    results: list[RenamePatternResult]
    error: str | None = None


class PolicyOut(BaseModel):
    """A policy as currently loaded by the engine."""

    id: str
    type: str
    enabled: bool
    severity: Severity
    compile_error: str | None = None


class PoliciesListResponse(BaseModel):
    """Policies currently loaded. `error` is non-null if the YAML file
    is invalid; in that case the last-good policies remain loaded."""

    error: str | None = None
    policies: list[PolicyOut]


class UpdatePoliciesResponse(BaseModel):
    ok: bool
    error: str | None = None
