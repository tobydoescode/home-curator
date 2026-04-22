"""GET / PUT /api/policies."""
from fastapi import APIRouter, Depends

from home_curator.api.deps import AppState, app_state
from home_curator.api.schemas import (
    PoliciesListResponse,
    PolicyCompileResponse,
    PolicyOut,
    UpdatePoliciesResponse,
)
from home_curator.config import Settings
from home_curator.policies.schema import PoliciesFile, Policy
from home_curator.policies.writer import write_policies_file
from home_curator.rules.custom_cel import compile_custom

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
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=state.policies_error or "Policies file invalid")
    return state.policies_file


@router.put("", response_model=UpdatePoliciesResponse)
def update_policies(body: PoliciesFile) -> UpdatePoliciesResponse:
    """Replace policies.yaml.

    The request body matches the YAML file's shape exactly — a tagged union
    keyed by `type`. Invalid bodies are rejected with 422 before the file is
    touched; the hot-reload watcher picks up the write and recompiles the
    engine.
    """
    data = body.model_dump(mode="json", by_alias=True)
    settings = Settings()
    write_policies_file(settings.policies_path, data)
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
