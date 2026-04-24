# Backend Pyright Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the remaining backend Pyright debt from the current `215 errors` to zero without weakening Pyright settings or adding broad ignores.

**Architecture:** Fix errors by cluster: SQLAlchemy storage typing first, policy-union narrowing second, test helper typing third. Each task should leave a focused slice Pyright-clean and covered by existing tests.

**Tech Stack:** Python 3.12+, Pyright, Pydantic v2 discriminated unions, SQLAlchemy 2.0, pytest, Ruff.

---

## Current Baseline

As of 2026-04-24 on `main` after the HA-client and rules cleanup merges:

```bash
cd apps/backend && uv run pyright src tests
```

Expected current result before this plan starts: `215 errors, 0 warnings, 0 informations`.

The major clusters are:

- `src/home_curator/storage/exceptions_repo.py`: `rowcount` access on generic SQLAlchemy `Result`.
- `src/home_curator/storage/types.py`: `TypeDecorator` override parameter name mismatch.
- Policy tests: Pydantic union values are accessed without narrowing to the concrete policy type.
- Rule tests: helper dictionaries infer overly broad `str | list[Any] | dict[Any, Any] | None` unions and are passed into strongly typed dataclasses.

---

## Task 1: Fix SQLAlchemy Storage Typing

**Files:**
- Modify: `apps/backend/src/home_curator/storage/exceptions_repo.py`
- Modify: `apps/backend/src/home_curator/storage/types.py`
- Test: `apps/backend/tests/unit/storage/test_exceptions_repo.py`
- Test: `apps/backend/tests/unit/storage/test_models.py`

- [ ] **Step 1: Verify the focused Pyright failures**

Run:

```bash
cd apps/backend && uv run pyright src/home_curator/storage
```

Expected: errors for `Result[Any].rowcount` and `TypeDecorator` parameter name mismatch.

- [ ] **Step 2: Fix `rowcount` typing in `exceptions_repo.py`**

Change the SQLAlchemy imports:

```python
from sqlalchemy import delete, func, or_, select
from sqlalchemy.engine import CursorResult
```

Add this helper near `TargetKind`:

```python
def _deleted_count(result: CursorResult[object]) -> int:
    return result.rowcount or 0
```

In `delete_not_in`, annotate the result variable:

```python
result: CursorResult[object]
if policy_ids:
    result = self.session.execute(
        delete(Exemption).where(Exemption.policy_id.notin_(policy_ids))
    )
else:
    result = self.session.execute(delete(Exemption))
return _deleted_count(result)
```

In `bulk_delete`, annotate the result variable:

```python
result: CursorResult[object] = self.session.execute(
    delete(Exemption).where(Exemption.id.in_(ids))
)
return _deleted_count(result)
```

Move the local `from sqlalchemy import func` import in `list_paginated` to the top-level import added above.

- [ ] **Step 3: Fix `TypeDecorator` override signatures**

In `apps/backend/src/home_curator/storage/types.py`, rename `_dialect` to `dialect` in both methods:

```python
def process_bind_param(self, value, dialect):
    del dialect
    if value is not None and value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value

def process_result_value(self, value, dialect):
    del dialect
    if value is not None:
        return value.replace(tzinfo=UTC)
    return value
```

- [ ] **Step 4: Verify storage typing and tests**

Run:

```bash
cd apps/backend
uv run pyright src/home_curator/storage
uv run pytest tests/unit/storage tests/unit/test_alembic_migration.py -q
```

Expected: Pyright reports `0 errors`; storage and migration tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/src/home_curator/storage/exceptions_repo.py apps/backend/src/home_curator/storage/types.py
git commit -m "fix(backend): clean up storage pyright errors"
```

---

## Task 2: Add Policy Union Narrowing Helpers For Tests

**Files:**
- Modify: `apps/backend/tests/unit/test_seed_policies_entity.py`
- Modify: `apps/backend/tests/integration/test_policies_entity_yaml_roundtrip.py`
- Modify: `apps/backend/tests/unit/policies/test_loader.py`

- [ ] **Step 1: Verify focused policy-test failures**

Run:

```bash
cd apps/backend && uv run pyright \
  tests/unit/test_seed_policies_entity.py \
  tests/integration/test_policies_entity_yaml_roundtrip.py \
  tests/unit/policies/test_loader.py
```

Expected: attribute-access errors on policy unions and one optional-member error in `test_loader.py`.

- [ ] **Step 2: Add local concrete-policy helpers in seed-policy tests**

At the top of `tests/unit/test_seed_policies_entity.py`, import concrete classes:

```python
from home_curator.policies.schema import (
    EntityMissingAreaPolicy,
    EntityNamingConventionPolicy,
    ReappearedAfterDeletePolicy,
)
```

Add helpers after the imports:

```python
def _entity_naming(result) -> EntityNamingConventionPolicy:
    assert result.file is not None
    policy = next(p for p in result.file.policies if p.id == "entity-naming-convention")
    assert isinstance(policy, EntityNamingConventionPolicy)
    return policy


def _entity_missing_area(result) -> EntityMissingAreaPolicy:
    assert result.file is not None
    policy = next(p for p in result.file.policies if p.id == "entity-missing-area")
    assert isinstance(policy, EntityMissingAreaPolicy)
    return policy


def _entity_reappeared(result) -> ReappearedAfterDeletePolicy:
    assert result.file is not None
    policy = next(p for p in result.file.policies if p.id == "entity-reappeared")
    assert isinstance(policy, ReappearedAfterDeletePolicy)
    return policy
```

Replace direct `next(...)` assignments for those policy ids with the helper that returns the concrete type before accessing `.name`, `.entity_id`, `.require_own_area`, or `.scope`.

- [ ] **Step 3: Add local concrete-policy helpers in roundtrip tests**

At the top of `tests/integration/test_policies_entity_yaml_roundtrip.py`, import concrete classes:

```python
from home_curator.policies.schema import (
    CustomPolicy,
    EntityMissingAreaPolicy,
    EntityNamingConventionPolicy,
    PoliciesFile,
    ReappearedAfterDeletePolicy,
)
```

Add helpers after `_mixed_policies`:

```python
def _policy_as(mapping: dict[str, object], policy_id: str, cls):
    policy = mapping[policy_id]
    assert isinstance(policy, cls)
    return policy
```

Use it before entity-specific assertions:

```python
en = _policy_as(by_id, "en", EntityNamingConventionPolicy)
ema = _policy_as(by_id, "ema", EntityMissingAreaPolicy)
c_ent = _policy_as(by_id, "c-ent", CustomPolicy)
r_ent = _policy_as(by_id, "r-ent", ReappearedAfterDeletePolicy)
```

Only access fields such as `.name`, `.entity_id`, `.require_own_area`, and `.scope` after the `isinstance` assertion.

- [ ] **Step 4: Fix optional access in `test_loader.py`**

In `apps/backend/tests/unit/policies/test_loader.py`, before calling `.lower()` on a possibly optional string, assert it is not `None`.

Use this pattern:

```python
assert result.error is not None
error = result.error.lower()
assert "unknown_type" in error
```

- [ ] **Step 5: Verify policy-test typing and tests**

Run:

```bash
cd apps/backend
uv run pyright \
  tests/unit/test_seed_policies_entity.py \
  tests/integration/test_policies_entity_yaml_roundtrip.py \
  tests/unit/policies/test_loader.py
uv run pytest \
  tests/unit/test_seed_policies_entity.py \
  tests/integration/test_policies_entity_yaml_roundtrip.py \
  tests/unit/policies/test_loader.py \
  -q
```

Expected: Pyright reports `0 errors` for these files; tests pass.

- [ ] **Step 6: Commit**

```bash
git add \
  apps/backend/tests/unit/test_seed_policies_entity.py \
  apps/backend/tests/integration/test_policies_entity_yaml_roundtrip.py \
  apps/backend/tests/unit/policies/test_loader.py
git commit -m "test(backend): narrow policy unions for pyright"
```

---

## Task 3: Type Rule-Test Factories

**Files:**
- Modify: `apps/backend/tests/unit/rules/test_custom_cel.py`
- Modify: `apps/backend/tests/unit/rules/test_custom_cel_entity_scope.py`
- Modify: `apps/backend/tests/unit/rules/test_missing_area_entity.py`
- Modify: `apps/backend/tests/unit/rules/test_naming_convention.py`
- Modify other files under `apps/backend/tests/unit/rules/` only if Pyright reports the same helper-inference pattern.

- [ ] **Step 1: Verify focused rule-test failures**

Run:

```bash
cd apps/backend && uv run pyright tests/unit/rules
```

Expected: errors where `defaults = dict(...)` plus `defaults.update(kw)` causes broad unions before constructing `Device`, `Entity`, or `EvaluationContext`.

- [ ] **Step 2: Replace broad `dict` factories with typed factories**

For device helpers, use an explicit return type and concrete constructor values:

```python
from typing import Any

from home_curator.rules.base import Device, EntitySummary


def _d(
    *,
    id: str = "d1",
    name: str = "n",
    name_by_user: str | None = None,
    manufacturer: str | None = "Aqara",
    model: str | None = None,
    area_id: str | None = None,
    area_name: str | None = None,
    integration: str | None = None,
    disabled_by: str | None = None,
    entities: list[EntitySummary] | None = None,
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
        state=state or {},
    )
```

For entity helpers, use the same pattern:

```python
from typing import Any

from home_curator.rules.base import Entity


def _e(
    *,
    entity_id: str = "light.lamp",
    name: str | None = "Lamp",
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
        state=state or {},
    )
```

For context helpers, use explicit arguments:

```python
from home_curator.rules.base import Device, EvaluationContext, TargetKind


def _ctx(
    *,
    area_name_to_id: dict[str, str] | None = None,
    area_id_to_name: dict[str, str] | None = None,
    exceptions: set[tuple[TargetKind, str, str]] | None = None,
    devices_by_id: dict[str, Device] | None = None,
) -> EvaluationContext:
    return EvaluationContext(
        area_name_to_id=area_name_to_id or {},
        area_id_to_name=area_id_to_name or {},
        exceptions=exceptions or set(),
        devices_by_id=devices_by_id or {},
    )
```

- [ ] **Step 3: Fix naming-convention policy helper signatures**

In `tests/unit/rules/test_naming_convention.py`, type `_policy` explicitly:

```python
from home_curator.policies.schema import NamingPreset, RoomOverride


def _policy(
    global_preset: NamingPreset = "snake_case",
    rooms: list[RoomOverride] | None = None,
) -> NamingConventionPolicy:
    return NamingConventionPolicy(
        id="nc",
        type="naming_convention",
        enabled=True,
        severity="warning",
        **{"global": NamingPatternConfig(preset=global_preset)},
        rooms=rooms or [],
    )
```

- [ ] **Step 4: Verify rule-test typing and tests**

Run:

```bash
cd apps/backend
uv run pyright tests/unit/rules
uv run pytest tests/unit/rules -q
```

Expected: Pyright reports `0 errors` for `tests/unit/rules`; rule tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/tests/unit/rules
git commit -m "test(backend): type rule test factories"
```

---

## Task 4: Full Pyright Verification

**Files:** none unless Tasks 1-3 expose a new diagnostic in their edited files.

- [ ] **Step 1: Run full Pyright**

```bash
cd apps/backend && uv run pyright src tests
```

Expected after Tasks 1-3: `0 errors, 0 warnings, 0 informations`.

- [ ] **Step 2: If Pyright still reports errors, classify before editing**

The current 215-error baseline is covered by Tasks 1-3. If this command still reports errors, do not guess or broaden the branch. Capture the first 80 lines:

```bash
cd apps/backend && uv run pyright src tests 2>&1 | head -n 80
```

Then classify the diagnostic as one of:

- A mistake in Tasks 1-3: fix it in the same branch and rerun the focused task verification.
- A new diagnostic caused by a dependency/tooling change: add a new task to this plan before editing.
- An unrelated old diagnostic that was not present in the current structured Pyright output: stop and ask for plan scope confirmation.

- [ ] **Step 3: Verify full backend type and test gates**

Run:

```bash
cd apps/backend
uv run pyright src tests
uv run pytest -q
```

Expected: Pyright reports `0 errors`; pytest passes.

- [ ] **Step 4: Commit final Pyright cleanup**

```bash
git add apps/backend/src apps/backend/tests
git commit -m "chore(backend): finish pyright cleanup"
```

---

## Final Verification

- [ ] **Step 1: Run final backend verification**

```bash
cd apps/backend
uv run pyright src tests
uv run pytest -q
```

Expected:

- `pyright`: `0 errors, 0 warnings, 0 informations`.
- `pytest`: all tests pass.

- [ ] **Step 2: Capture remaining non-Pyright work**

Run:

```bash
cd apps/backend
uv run ruff check src tests
uv run pytest -q
```

Expected: Ruff and warning debt may remain for the dedicated follow-up plans; do not expand this Pyright branch into lint or deprecation cleanup unless needed to keep changed files locally clean.
