"""GET / PUT /api/policies."""
from celpy.adapter import json_to_cel
from fastapi import APIRouter, Depends, HTTPException

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import (
    PoliciesListResponse,
    PolicyCompileResponse,
    PolicyOut,
    SimulateCounts,
    SimulateRequest,
    SimulateResponse,
    SimulateTargetRow,
    UpdatePoliciesResponse,
)
from home_curator.config import Settings
from home_curator.policies.schema import CustomPolicy, PoliciesFile, Policy
from home_curator.policies.writer import write_policies_file
from home_curator.rules.base import Device, Entity
from home_curator.rules.custom_cel import compile_custom
from home_curator.storage.db import session_scope
from home_curator.storage.exceptions_repo import ExceptionsRepo

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.get("", response_model=PoliciesListResponse)
def list_policies(state: AppState = Depends(app_state)) -> PoliciesListResponse:
    """List all policies currently loaded by the engine.

    The `error` field is non-null if the YAML file is invalid; in that case
    the last-good policies remain loaded and are returned in `policies`.
    """
    if state.policies_file is None:
        return PoliciesListResponse(error=state.policies_error, policies=[])
    errors = state.engine.compile_errors()
    return PoliciesListResponse(
        error=None,
        policies=[
            PolicyOut(
                id=p.id,
                type=p.type,
                enabled=p.enabled,
                severity=p.severity,
                compile_error=errors.get(p.id),
            )
            for p in state.policies_file.policies
        ],
    )


@router.get("/file", response_model=PoliciesFile)
def get_policies_file(state: AppState = Depends(app_state)) -> PoliciesFile:
    """Return the fully-typed policies file (all fields, not a summary).

    Used by the authoring UI so it can round-trip every field without loss.
    Invalid-file case: returns 503 rather than an empty body, since the client
    is expecting edit-ready data.
    """
    if state.policies_file is None:
        raise HTTPException(status_code=503, detail=state.policies_error or "Policies file invalid")
    return state.policies_file


@router.put("", response_model=UpdatePoliciesResponse)
async def update_policies(body: PoliciesFile, state: AppState = Depends(app_state)) -> UpdatePoliciesResponse:
    """Replace policies.yaml.

    After writing, cascade-delete any exceptions that reference a policy_id
    no longer present in the file. Emits one `exceptions_changed` SSE event
    so open Exceptions pages refresh.
    """
    data = body.model_dump(mode="json", by_alias=True)
    settings = Settings()
    write_policies_file(settings.policies_path, data)

    kept_ids = {p.id for p in body.policies}
    with session_scope(state.session_factory) as s:
        deleted = ExceptionsRepo(s).delete_not_in(kept_ids)
    if deleted > 0:
        await state.broker.publish({"kind": "exceptions_changed"})
    return UpdatePoliciesResponse(ok=True)


@router.post("/compile", response_model=PolicyCompileResponse)
def compile_policy(body: Policy) -> PolicyCompileResponse:
    """Compile a draft policy without persisting it.

    Returns ok=True if the compiled rule has no compile_error, otherwise
    ok=False with the error string. Non-custom types currently have no
    compile step beyond schema validation; they always return ok=True
    once the body parses.
    """
    if body.type == "custom":
        rule = compile_custom(body)
        if rule.compile_error:
            return PolicyCompileResponse(ok=False, error=rule.compile_error)
    return PolicyCompileResponse(ok=True)


@router.post("/simulate", response_model=SimulateResponse)
def simulate_policy(
    body: SimulateRequest, state: AppState = Depends(app_state)
) -> SimulateResponse:
    """Run a custom rule against the full device OR entity set depending
    on the policy's `scope`. Non-custom rule types return ok=True with
    zero counts; simulation only makes sense for user-authored CEL.
    """
    policy = body.policy
    if policy is None:
        if state.policies_file is None:
            return SimulateResponse(ok=False, error="Policies file invalid")
        policy = next(
            (p for p in state.policies_file.policies if p.id == body.policy_id), None,
        )
        if policy is None:
            return SimulateResponse(ok=False, error=f"No policy with id {body.policy_id!r}")

    if not isinstance(policy, CustomPolicy):
        return SimulateResponse(
            ok=True,
            counts=SimulateCounts(matched_when=0, passes_assert=0, fails_assert=0, errored=0),
        )

    rule = compile_custom(policy)
    if rule.compile_error:
        return SimulateResponse(ok=False, error=rule.compile_error)

    if policy.scope == "entities":
        return _simulate_entities(rule, state)
    return _simulate_devices(rule, state)


def _simulate_devices(rule, state: AppState) -> SimulateResponse:
    all_devices = state.cache.devices()
    tracker_state = state.tracker.all_state()
    hydrated = [
        Device(
            id=d.id, name=d.name, name_by_user=d.name_by_user,
            manufacturer=d.manufacturer, model=d.model,
            area_id=d.area_id, area_name=d.area_name,
            integration=d.integration, disabled_by=d.disabled_by,
            entities=d.entities, state=tracker_state.get(d.id, {}),
        )
        for d in all_devices
    ]
    matched_when = 0
    failing: list[SimulateTargetRow] = []
    errored: list[SimulateTargetRow] = []
    passing: list[SimulateTargetRow] = []
    # Simulator runs raw CEL — acknowledged exceptions are intentionally not applied here.
    for d in hydrated:
        cel_ctx = {"device": json_to_cel(d.to_cel_context())}
        try:
            if rule._when is not None and not bool(rule._when.evaluate(cel_ctx)):
                continue
            matched_when += 1
            ok = bool(rule._assert.evaluate(cel_ctx))
        except Exception as e:  # noqa: BLE001
            errored.append(SimulateTargetRow(
                id=d.id, name=d.display_name, room=d.area_name, error=str(e),
            ))
            continue
        row = SimulateTargetRow(id=d.id, name=d.display_name, room=d.area_name)
        if ok:
            passing.append(row)
        else:
            row.message = rule.message
            failing.append(row)
    return SimulateResponse(
        ok=True,
        counts=SimulateCounts(
            matched_when=matched_when,
            passes_assert=len(passing),
            fails_assert=len(failing),
            errored=len(errored),
        ),
        failing=failing, errored=errored, passing=passing,
    )


def _simulate_entities(rule, state: AppState) -> SimulateResponse:
    area_id_to_name = state.cache.area_id_to_name()
    devices_by_id: dict[str, Device] = {
        d.id: Device(
            id=d.id, name=d.name, name_by_user=d.name_by_user,
            manufacturer=d.manufacturer, model=d.model,
            area_id=d.area_id, area_name=d.area_name,
            integration=d.integration, disabled_by=d.disabled_by,
            entities=d.entities,
        )
        for d in state.cache.devices()
    }
    all_entities: list[Entity] = state.entity_cache.entities()
    matched_when = 0
    failing: list[SimulateTargetRow] = []
    errored: list[SimulateTargetRow] = []
    passing: list[SimulateTargetRow] = []
    for e in all_entities:
        owning = devices_by_id.get(e.device_id) if e.device_id else None
        # Effective area: entity's own first, else owning device's (same
        # convention as the rule engine's entity-scope evaluator).
        effective_area_id = e.area_id or (owning.area_id if owning else None)
        area_name = (
            area_id_to_name.get(effective_area_id) if effective_area_id else None
        )
        entity_ctx = e.to_cel_context(
            device_context=owning.to_cel_context() if owning is not None else None,
            area_name=area_name,
        )
        cel_ctx = {"entity": json_to_cel(entity_ctx)}
        try:
            if rule._when is not None and not bool(rule._when.evaluate(cel_ctx)):
                continue
            matched_when += 1
            ok = bool(rule._assert.evaluate(cel_ctx))
        except Exception as ex:  # noqa: BLE001
            errored.append(SimulateTargetRow(
                id=e.entity_id, name=e.display_name, room=area_name, error=str(ex),
            ))
            continue
        row = SimulateTargetRow(
            id=e.entity_id, name=e.display_name, room=area_name,
        )
        if ok:
            passing.append(row)
        else:
            row.message = rule.message
            failing.append(row)
    return SimulateResponse(
        ok=True,
        counts=SimulateCounts(
            matched_when=matched_when,
            passes_assert=len(passing),
            fails_assert=len(failing),
            errored=len(errored),
        ),
        failing=failing, errored=errored, passing=passing,
    )
