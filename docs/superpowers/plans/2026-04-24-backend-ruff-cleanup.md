# Backend Ruff Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `cd apps/backend && uv run ruff check src tests` pass without disabling existing Ruff rules.

**Architecture:** Fix violations in three passes: API FastAPI parameter defaults, import ordering, then line-length and test import placement. Keep changes mechanical and behavior-preserving.

**Tech Stack:** Ruff, FastAPI, pytest, Python 3.12+.

---

## Current Baseline

As of 2026-04-24 on `main` after the Pyright config/rules cleanup:

```bash
cd apps/backend && uv run ruff check src tests
```

Expected current result before this plan starts: `61 errors`.

Known clusters:

- `B008`: FastAPI `Depends(...)` and `Query(...)` calls in route default arguments.
- `I001`: import blocks requiring Ruff sorting.
- `E501`: long lines in API modules and tests.
- `E402`: late imports in `tests/unit/storage/test_exceptions_repo.py`.

---

## Task 1: Fix API FastAPI `B008` Defaults

**Files:**
- Modify: `apps/backend/src/home_curator/api/actions.py`
- Modify: `apps/backend/src/home_curator/api/areas.py`
- Modify: `apps/backend/src/home_curator/api/entities.py`
- Modify: `apps/backend/src/home_curator/api/events.py`
- Modify: `apps/backend/src/home_curator/api/exceptions.py`
- Modify: `apps/backend/src/home_curator/api/policies.py`
- Test: API and integration tests under `apps/backend/tests/integration`

- [ ] **Step 1: Verify API Ruff failures**

Run:

```bash
cd apps/backend && uv run ruff check src/home_curator/api
```

Expected: `B008` errors in route signatures plus some `E501`/`I001` errors.

- [ ] **Step 2: Add module-level dependency/query singletons**

For each API module with `Depends(app_state)` in defaults, add this near the router definition:

```python
_APP_STATE_DEPENDENCY = Depends(app_state)
```

Replace route defaults like:

```python
state: AppState = Depends(app_state)
```

with:

```python
state: AppState = _APP_STATE_DEPENDENCY
```

For repeated list query params, use one singleton per semantic parameter, not one shared object for unrelated fields:

```python
_DOMAIN_QUERY = Query(default_factory=list)
_ROOM_QUERY = Query(default_factory=list)
_INTEGRATION_QUERY = Query(default_factory=list)
_ISSUE_TYPE_QUERY = Query(default_factory=list)
_POLICY_ID_QUERY = Query(default_factory=list)
_DEVICE_ID_QUERY = Query(default_factory=list)
_ENTITY_ID_QUERY = Query(default_factory=list)
_AREA_ID_QUERY = Query(default_factory=list)
_PAGE_QUERY = Query(default=1, ge=1)
_PAGE_SIZE_QUERY = Query(default=50, ge=1, le=500)
```

Then replace defaults like:

```python
domain: list[str] = Query(default_factory=list)
```

with:

```python
domain: list[str] = _DOMAIN_QUERY
```

- [ ] **Step 3: Preserve OpenAPI behavior**

After changing API defaults, run:

```bash
cd apps/backend && uv run python - <<'PY'
from home_curator.main import create_app

schema = create_app().openapi()
assert "/api/entities" in schema["paths"]
assert "/api/actions/assign-room" in schema["paths"]
assert "/api/exceptions" in schema["paths"]
print("openapi ok")
PY
```

Expected: prints `openapi ok`.

- [ ] **Step 4: Verify API tests**

Run:

```bash
cd apps/backend && uv run pytest tests/integration -q
```

Expected: integration tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/src/home_curator/api
git commit -m "style(backend): move fastapi route defaults to module constants"
```

---

## Task 2: Apply Ruff Import Sorting

**Files:**
- Modify: files reported by `I001` from `uv run ruff check src tests`.

- [ ] **Step 1: Run Ruff import fixes**

Run:

```bash
cd apps/backend && uv run ruff check src tests --select I --fix
```

Expected: Ruff updates import ordering only.

- [ ] **Step 2: Review the diff**

Run:

```bash
git diff -- apps/backend/src apps/backend/tests
```

Expected: import ordering only. If unrelated formatting changed, inspect it before committing.

- [ ] **Step 3: Verify import sorting**

Run:

```bash
cd apps/backend && uv run ruff check src tests --select I
```

Expected: `All checks passed!`.

- [ ] **Step 4: Commit**

```bash
git add apps/backend/src apps/backend/tests
git commit -m "style(backend): sort imports with ruff"
```

---

## Task 3: Fix Long Lines And Late Imports

**Files:**
- Modify: `apps/backend/src/home_curator/api/actions.py`
- Modify: `apps/backend/src/home_curator/api/exceptions.py`
- Modify: `apps/backend/src/home_curator/api/policies.py`
- Modify: `apps/backend/tests/integration/test_policies_hot_reload.py`
- Modify: `apps/backend/tests/unit/policies/test_loader.py`
- Modify: `apps/backend/tests/unit/policies/test_schema.py`
- Modify: `apps/backend/tests/unit/rules/test_naming_convention.py`
- Modify: `apps/backend/tests/unit/rules/test_reappeared.py`
- Modify: `apps/backend/tests/unit/storage/test_exceptions_repo.py`
- Modify: `apps/backend/tests/unit/test_entity_cache.py`

- [ ] **Step 1: Re-run full Ruff**

Run:

```bash
cd apps/backend && uv run ruff check src tests
```

Expected: the output is limited to `E501`, `E402`, and possibly `B904`.

- [ ] **Step 2: Split long route signatures**

Use this style for long route functions:

```python
async def rename_pattern(
    body: RenamePatternBody,
    state: AppState = _APP_STATE_DEPENDENCY,
) -> RenamePatternResponse:
```

Use this style for long response construction:

```python
results.append(
    RenamePatternResult(
        device_id=did,
        matched=True,
        new_name=new,
        ok=True,
    )
)
```

- [ ] **Step 3: Add exception chaining where Ruff reports `B904`**

Replace:

```python
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```

with:

```python
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e)) from e
```

If the original exception intentionally should be hidden, use `from None` and add a short comment explaining why.

- [ ] **Step 4: Move late imports to the top of test files**

For `tests/unit/storage/test_exceptions_repo.py`, move late imports such as:

```python
from datetime import UTC, datetime

from home_curator.storage.db import session_scope
from home_curator.storage.models import Exemption
```

to the top import block. Remove duplicate lower imports.

- [ ] **Step 5: Split long test data lines**

Use parenthesized multiline calls:

```python
s.add(
    Exemption(
        device_id="d1",
        policy_id="p1",
        acknowledged_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
)
```

For long strings, use adjacent strings inside parentheses:

```python
p.write_text(
    "version: 1\n"
    "policies:\n"
    "  - id: x\n"
    "    type: unknown_type\n"
    "    severity: info\n"
    "    enabled: true\n"
)
```

- [ ] **Step 6: Verify full Ruff and tests**

Run:

```bash
cd apps/backend
uv run ruff check src tests
uv run pytest -q
```

Expected: Ruff passes; all tests pass.

- [ ] **Step 7: Commit**

```bash
git add apps/backend/src apps/backend/tests
git commit -m "style(backend): finish ruff cleanup"
```

---

## Final Verification

- [ ] **Step 1: Run backend verification**

```bash
cd apps/backend
uv run ruff check src tests
uv run pytest -q
```

Expected:

- Ruff: `All checks passed!`.
- Pytest: all tests pass.

- [ ] **Step 2: Check Pyright was not regressed**

Run:

```bash
cd apps/backend && uv run pyright src tests
```

Expected: if the Pyright cleanup plan has already landed, `0 errors`; otherwise no increase from the pre-Ruff-cleanup baseline.
