# Backend Test Warning Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `cd apps/backend && uv run pytest -q` pass without the current recurring deprecation warnings.

**Architecture:** Fix warnings at their source when practical. Alembic warning is a config fix. WebSocket warnings are dependency-stack warnings emitted by `uvicorn[standard]` during real-SSE integration tests, so first attempt to configure Uvicorn away from deprecated websockets internals; if the installed Uvicorn version cannot avoid them, isolate warning filters to those integration tests with exact messages.

**Tech Stack:** pytest, Uvicorn, websockets, Alembic, FastAPI.

---

## Current Baseline

As of 2026-04-24 on `main`:

```bash
cd apps/backend && uv run pytest -q
```

Expected current result before this plan starts: all tests pass with `5 warnings`.

Known warnings:

- `websockets.legacy is deprecated` from `websockets/legacy/__init__.py`.
- `websockets.server.WebSocketServerProtocol is deprecated` from `uvicorn/protocols/websockets/websockets_impl.py`.
- Alembic `No path_separator found in configuration` from `alembic/config.py`.

---

## Task 1: Fix Alembic `path_separator` Warning

**Files:**
- Modify: `apps/backend/alembic.ini`
- Test: `apps/backend/tests/unit/test_alembic_migration.py`

- [ ] **Step 1: Verify the Alembic warning**

Run:

```bash
cd apps/backend && uv run pytest tests/unit/test_alembic_migration.py -q
```

Expected: tests pass and emit Alembic `No path_separator found in configuration`.

- [ ] **Step 2: Add `path_separator = os`**

In `apps/backend/alembic.ini`, update the `[alembic]` section:

```ini
[alembic]
script_location = alembic
prepend_sys_path = src
path_separator = os
sqlalchemy.url =
```

- [ ] **Step 3: Verify the warning is gone**

Run:

```bash
cd apps/backend && uv run pytest tests/unit/test_alembic_migration.py -q
```

Expected: tests pass with no Alembic `path_separator` warning.

- [ ] **Step 4: Commit**

```bash
git add apps/backend/alembic.ini
git commit -m "chore(backend): configure alembic path separator"
```

---

## Task 2: Remove Or Isolate Uvicorn/Websockets Deprecation Warnings

**Files:**
- Modify: `apps/backend/tests/integration/test_events_sse.py`
- Modify: `apps/backend/tests/integration/test_events_entity_sse.py`
- Modify: `apps/backend/tests/integration/test_registry_event_refresh.py` only if it emits the same warning under focused execution.

- [ ] **Step 1: Verify focused warning source**

Run:

```bash
cd apps/backend && uv run pytest \
  tests/integration/test_events_sse.py \
  tests/integration/test_events_entity_sse.py \
  tests/integration/test_registry_event_refresh.py \
  -q
```

Expected: tests pass and emit one or more websockets deprecation warnings.

- [ ] **Step 2: Try Uvicorn's non-legacy websocket backend first**

In each test file that constructs `uvicorn.Config`, add `ws="wsproto"`:

```python
config = uvicorn.Config(
    app=app_with_fake,
    host="127.0.0.1",
    port=port,
    log_level="error",
    loop="asyncio",
    ws="wsproto",
)
```

If the test helper uses a different app variable name, keep that variable and add only `ws="wsproto"`.

- [ ] **Step 3: Verify the focused SSE tests**

Run:

```bash
cd apps/backend && uv run pytest \
  tests/integration/test_events_sse.py \
  tests/integration/test_events_entity_sse.py \
  tests/integration/test_registry_event_refresh.py \
  -q
```

Expected: tests pass. If websocket deprecation warnings are gone, skip Step 4.

- [ ] **Step 4: If Uvicorn still emits dependency warnings, add exact local filters**

Only if Step 3 still emits the warnings, add `pytestmark` near the imports of each emitting test module:

```python
pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:websockets\\.legacy is deprecated:DeprecationWarning"
    ),
    pytest.mark.filterwarnings(
        "ignore:websockets\\.server\\.WebSocketServerProtocol is deprecated:DeprecationWarning"
    ),
]
```

Do not add broad `ignore::DeprecationWarning` filters. The filters must match only the known third-party warnings.

- [ ] **Step 5: Commit**

```bash
git add \
  apps/backend/tests/integration/test_events_sse.py \
  apps/backend/tests/integration/test_events_entity_sse.py \
  apps/backend/tests/integration/test_registry_event_refresh.py
git commit -m "test(backend): remove websocket deprecation noise"
```

---

## Task 3: Enforce Warning-Free Test Output

**Files:**
- Modify: `apps/backend/pyproject.toml`

- [ ] **Step 1: Confirm full suite is warning-free before enforcing**

Run:

```bash
cd apps/backend && uv run pytest -q
```

Expected: tests pass and warnings summary is absent. If warnings remain, fix or explicitly isolate them before continuing.

- [ ] **Step 2: Add warning strictness for project tests**

In `apps/backend/pyproject.toml`, update `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
asyncio_mode = "auto"
filterwarnings = [
    "error::DeprecationWarning:home_curator.*",
]
```

This makes deprecations from project code fail tests while avoiding immediate breakage from unrelated third-party internals.

- [ ] **Step 3: Verify full suite**

Run:

```bash
cd apps/backend && uv run pytest -q
```

Expected: all tests pass and no warnings summary is printed.

- [ ] **Step 4: Commit**

```bash
git add apps/backend/pyproject.toml
git commit -m "test(backend): enforce project deprecation warnings"
```

---

## Final Verification

- [ ] **Step 1: Run backend tests**

```bash
cd apps/backend && uv run pytest -q
```

Expected: all tests pass with no warnings summary.

- [ ] **Step 2: Check lint/type gates if prior plans have landed**

Run:

```bash
cd apps/backend
uv run ruff check src tests
uv run pyright src tests
```

Expected: if the Ruff and Pyright cleanup plans have already landed, both commands pass. If not, do not fix unrelated Ruff/Pyright debt in this warning branch.
