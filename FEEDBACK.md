# Home Curator — Repository Review

Review date: 2026-07-27. Commit: `54c1672`.

## How this was verified

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `uv run pytest -q` | **381 passed** |
| Frontend tests | `npm run test:run` | **159 passed** (40 files) |
| Backend lint | `uv run ruff check src tests` | clean |
| Backend types | `uv run mypy src` | **1 error** (see F-4) |
| Backend tests from clean checkout | `task test:backend` | **fails** — deps not installed (see T-1) |

Everything below is grounded in the code as it stands. Items marked *(unverified at runtime)* are read from the source and packaging config but were not reproduced against a live Home Assistant instance.

---

## Severity summary

| ID | Severity | Area | Issue |
| --- | --- | --- | --- |
| C-1 | ~~Critical~~ **fixed** | Packaging | Frontend uses absolute paths; breaks under HA ingress |
| C-2 | ~~Critical~~ **fixed** | Release | Docker tag (`v0.1.0`) doesn't match the tag the Supervisor pulls (`0.1.0`) |
| C-3 | ~~Critical~~ **fixed** | First run | `CONFIG_DIR` is never created — first policy save 500s |
| C-4 | ~~High~~ **fixed** | Correctness | `/api/exceptions/list` applies `area_id` filter *after* pagination |
| C-5 | High | Config | `Settings()` re-instantiated in request handlers, ignoring injected settings |
| C-6 | ~~High~~ **fixed (partly wrong as filed)** | Concurrency | Compiled rules mutate themselves during evaluation |
| C-7 | ~~High~~ **fixed** | Data safety | `policies.yaml` written non-atomically |
| C-8 | ~~High~~ **fixed** | CI | mypy is documented but never run; it currently fails |
| C-9 | ~~Critical~~ **fixed** | Packaging | The addon image had never built — three independent faults |

---

## 1. Critical / blocking

### C-1 — The packaged frontend cannot load under HA ingress — **fixed**

> **Status: fixed.** The backend now injects `<base href>` from the
> `X-Ingress-Path` header (`api/spa.py`), Vite builds with `base: "./"`, and the
> API client, SSE subscription and router basename all resolve against
> `document.baseURI`. Guarded by `tests/e2e/` — an HTTP layer that follows the
> page's own asset and API URLs, and a Chromium layer that confirms the app
> actually boots under the prefix. Both were verified to fail when the
> respective defect is reintroduced. The description below is kept for context.


`home-curator/config.yaml:17-18` declares `ingress: true`. Home Assistant serves an ingress add-on under a path prefix (`/api/hassio_ingress/<session>/…`), which means every asset and API path the SPA emits must be **relative** to that prefix.

Three places emit absolute paths:

- `apps/frontend/dist/index.html:23-24` — `src="/assets/index-*.js"`, `href="/assets/index-*.css"`. `apps/frontend/vite.config.ts` sets no `base`, so Vite defaults to `/`.
- `apps/frontend/src/api/client.ts:7-15` — `baseUrl` is `window.location.origin`, so every request resolves to `https://<ha-host>/api/devices` rather than the add-on.
- `apps/frontend/src/api/sse.ts:13` — `new EventSource("/api/events")`, same problem.

Under ingress all of these hit Home Assistant core, not the add-on. Nothing in the repo references `import.meta.env.BASE_URL` (grepped), so there is no compensating mechanism.

**Fix:**

```ts
// vite.config.ts
export default defineConfig({ base: "./", /* … */ });
```

```ts
// api/client.ts — derive from the <base> the ingress page is served under
const baseUrl = document.baseURI.replace(/\/$/, "");
export const api = createClient<paths>({ baseUrl, fetch });
```

```ts
// api/sse.ts
const src = new EventSource(new URL("api/events", document.baseURI));
```

With `base: "./"` Vite emits relative asset paths and `document.baseURI` resolves to the ingress prefix. Add an integration check to CI that asserts `dist/index.html` contains no `src="/`.

### C-2 — Released image tag doesn't match the tag the Supervisor pulls — **fixed**

> **Status: fixed.** `release.yml` now strips a leading `v`, publishes
> `<image>:<version>`, and refuses to build if the tag and `config.yaml`
> disagree. `tests/unit/test_addon_metadata.py` fails the normal backend suite
> when `config.yaml` and `CHANGELOG.md` drift, so a forgotten bump is caught on
> the pull request rather than at release. The release process is documented in
> `home-curator/README.md`.
>
> Note for accuracy: the repo has **no git tags**, so nothing had ever been
> released and no user was affected — this blocked the *first* release rather
> than breaking an existing one. Version stays `0.1.0`; the CHANGELOG's two
> entries were consolidated into a single `0.1.0` covering everything actually
> built (which also closes D-2), since there was no released `0.1.0` for anyone
> to have upgraded from.


- `.github/workflows/release.yml:62` pushes `ghcr.io/<owner>/home-curator-<arch>:${{ github.ref_name }}` — for tag `v0.1.0` this is `:v0.1.0`.
- `home-curator/config.yaml:2,21` declares `version: "0.1.0"` and `image: ghcr.io/tobydoescode/home-curator-{arch}`. The Supervisor pulls `<image>:<version>` — i.e. `:0.1.0`, **without** the `v`.

Installation fails with a manifest-not-found. Additionally `config.yaml` is never bumped by the release workflow, so publishing `v0.2.0` leaves the add-on advertising `0.1.0` and users get no update prompt. `home-curator/CHANGELOG.md:1` already documents a `0.2.0` that `config.yaml` has never reflected.

**Fix:** strip the `v` when tagging, and make the release job assert (or rewrite) `config.yaml`'s `version`:

```yaml
- name: Derive version
  run: echo "VERSION=${GITHUB_REF_NAME#v}" >> "$GITHUB_ENV"
- name: Check add-on version matches tag
  run: |
    declared=$(yq '.version' home-curator/config.yaml)
    [ "$declared" = "$VERSION" ] || { echo "config.yaml=$declared tag=$VERSION"; exit 1; }
# …
    tags: ghcr.io/${{ github.repository_owner }}/home-curator-${{ matrix.arch }}:${{ env.VERSION }}
```

### C-3 — First run cannot save policies: `CONFIG_DIR` is never created — **fixed**

> **Status: fixed.** `write_policies_file` now creates its parent directory
> instead of refusing, so the invariant is owned by the function that needs it
> regardless of which `Settings` instance produced the path. Startup calls a new
> `seed_policies_file`, which writes the baseline file when absent — that both
> creates `/config/home-curator` and makes the README's "edit it directly"
> instruction true. Seeding never overwrites an existing file, and a failure is
> logged rather than fatal, so a read-only config mount still boots a working
> read-only app. `PUT /api/policies` now catches `OSError` and returns a 500
> naming the path and the OS error instead of a bare stack trace.
>
> Covered by `tests/integration/test_policies_first_run.py`, which deliberately
> does *not* pre-create `config_dir` — the thing every other fixture and
> `task setup` was doing, which is why this was invisible. Verified by reverting
> the writer fix: 3 tests go red.
>
> The README's first-run paragraph is rewritten (it also referenced the removed
> "Settings → Naming Conventions" route), and `loader.py`'s comment claiming the
> baseline "is written on first run" is now true rather than aspirational.


`storage/db.py:10` creates `data_dir` via `mkdir(parents=True, exist_ok=True)`. Nothing does the equivalent for `config_dir` — grepping `src/` for `mkdir` returns exactly one hit. So on a fresh install where `/config/home-curator/` does not exist:

- `policies/writer.py:16` raises `FileNotFoundError("parent directory does not exist: …")`,
- which `api/policies.py:79` does not catch,
- so `PUT /api/policies` returns an unhandled 500.

The add-on README compounds this: `home-curator/README.md:7` states *"On first start a default `policies.yaml` is created at `/config/home-curator/policies.yaml`"*. That is not true — `policies/loader.py:138-139` returns in-memory defaults for a missing file and never writes them. `loader.py:12-13`'s own comment ("the whole list is written on first run") describes behaviour that doesn't exist.

**Fix:** create the directory during lifespan startup, next to the `make_engine` call in `main.py`, and optionally seed the baseline file so the documented behaviour becomes true:

```python
effective_settings.config_dir.mkdir(parents=True, exist_ok=True)
```

Then correct the README, or implement the seed-on-first-run the README promises. Pick one — right now they disagree.

### C-4 — `/api/exceptions/list` filters by area after paginating — **fixed**

> **Status: fixed**, and it turned out to be three defects rather than one.
>
> 1. **Filtering after pagination.** Area filtering ran in Python against a
>    single already-paginated page, so matches beyond page one were
>    unreachable and `total` reported a per-page count. Area ids are now
>    resolved to device and entity ids up front and pushed into the query via
>    a new `targets_in_area` parameter, so `LIMIT`/`OFFSET` apply to the
>    filtered set. The pair is ORed, not ANDed — a row carries exactly one of
>    the two target columns, so ANDing them would match nothing.
> 2. **Entities were matched on their own `area_id`**, which is only an
>    override. An entity inheriting its area from its device was invisible to
>    the filter, contradicting `/api/entities`, which matches on the resolved
>    area. Both now agree.
> 3. **`bulk_delete` echoed back the requested ids**, claiming success for
>    rows that never existed. The repository now returns the ids it actually
>    deleted.
>
> Covered by `tests/integration/test_exceptions_area_filter.py` (10 tests) —
> there was no coverage of this parameter at all. All five relevant tests were
> confirmed failing before the fix.
>
> Still true, and separate: the filter is unreachable from the UI —
> `useExceptions.ts` plumbs `area_id` through but `ExceptionsPage.tsx` never
> passes it. That is F-2's territory.

`api/exceptions.py:124-154`:

```python
rows, total = ExceptionsRepo(s).list_paginated(...)   # already LIMIT/OFFSET'd
...
if area_id:
    rows = filtered            # filters only the current page
    total = len(rows)          # "total" is now a per-page count
```

Consequences: a page-2 request drops all page-1 matches; `total` no longer describes the result set, so `PaginationFooter` renders wrong page counts; and a filter that matches 60 rows spread across pages shows at most `page_size` of them.

**Fix:** push area filtering into the query, or resolve the area→target-id set first and pass it as `device_ids` / `entity_ids` into `list_paginated` so `LIMIT`/`OFFSET` apply to the filtered set.

Related, same file: `bulk_delete` (`api/exceptions.py:215`) returns `deleted=sorted(ids)` — the *requested* ids, not the deleted ones. `ExceptionsRepo.bulk_delete` already returns a real count that is thrown away. Callers cannot distinguish "deleted 5" from "4 of your 5 ids didn't exist".

### C-5 — `Settings()` is rebuilt inside request handlers, discarding injected settings

`create_app(ha_client=…, settings=…)` (`main.py:76`) takes a `Settings` and threads it through the lifespan. But two handlers ignore it and construct their own:

- `api/policies.py:78-79` — `settings = Settings(); write_policies_file(settings.policies_path, data)`
- `api/config_api.py:19` — `s = Settings()`

So `create_app(settings=X)` writes policies to whatever the *environment* says, not `X`. The integration tests only pass because `tests/integration/conftest.py:176-178` monkeypatches the env as well as passing `Settings()`. It also means every `GET /api/config` re-reads `.env` off disk.

**Fix:** put `Settings` on `AppState` (`api/deps.py:16`) alongside the other wiring and read `state.settings` in handlers. That makes the dependency explicit and removes the hidden filesystem read per request.

### C-6 — Compiled rules mutate shared state during evaluation — **fixed, and partly wrong as filed**

> **Correction first.** This item claimed the lazy room-override promotion in
> `naming_convention.evaluate()` was a live cross-thread race. It was not.
> `compile_naming_convention` only populated `pending_room_overrides` when
> `ctx is None`, and `RuleEngine.compile` has always passed a ctx, so that
> branch was unreachable in production. I asserted a race from reading the
> code without checking whether the branch could execute. The severity was
> overstated.
>
> **What was actually real** was the item I filed as a footnote: `DeletionTracker`
> state is written from the event loop (`handle_diff_from_cache`, via HA event
> callbacks) and read from FastAPI's threadpool (`all_state()` from
> `list_devices` and the simulator). Iterating a dict while another thread
> inserts raises `RuntimeError: dictionary changed size during iteration` and
> fails the request. Reproduced under a reduced thread-switch interval, then
> fixed with a lock whose critical sections deliberately exclude the database
> work.
>
> The dead lazy-resolution path is removed regardless: it made `evaluate()`
> look impure and would have become the race I wrongly described the moment
> anything compiled without a ctx. `ctx` is now required and overrides resolve
> once, at compile time.
>
> That change had a real consequence I nearly shipped silently. Creating an
> HA area used to activate a room override that named it, via the lazy
> promotion. With compile-time resolution that only happens on recompile, so
> `area_registry_updated` now rebuilds the engine.
> `tests/integration/test_area_change_recompiles.py` covers it, and was
> confirmed failing without the recompile.
>
> `CompiledCustom.runtime_errors` is deleted. It was incremented on every CEL
> runtime error and **never read anywhere** — mutation of shared state for no
> benefit.

`rules/naming_convention.py:127-137`, inside `evaluate()`:

```python
if self.pending_room_overrides:
    still_pending = []
    for room_name, entry in self.pending_room_overrides:
        ...
        self.overrides_by_area_id[resolved] = entry
        if room_name in self.unresolved_room_names:
            self.unresolved_room_names.remove(room_name)
    self.pending_room_overrides = still_pending
```

`list_devices` and `list_entities` are `def` (not `async def`) handlers, so FastAPI runs them in a threadpool — two concurrent requests execute `evaluate()` against the *same* `CompiledNamingConvention` instance and race on three mutable attributes. It also means `compile_error` (`naming_convention.py:114-118`) silently flips from an error string to `None` as a side effect of somebody listing devices, so `GET /api/policies`'s `compile_error` field is order-dependent.

`rules/custom_cel.py:93-94` has the milder version of the same shape (`self.runtime_errors += 1`).

Two adjacent races worth the same fix:

- `deletion_tracker.py:72-73` — `all_state()` builds a dict comprehension over `self._state` from a threadpool worker while event-loop callbacks (`main.py:133-153`) rewrite `self._state`. Concurrent mutation during iteration raises `RuntimeError: dictionary changed size during iteration`.
- `main.py:118-119` — one long-lived `Session` is shared by the tracker across all event-loop tasks. SQLAlchemy `Session` is not thread-safe or task-safe.

**Fix:** make `evaluate()` pure. Resolve room overrides once at compile time (the engine is recompiled on every policy reload and on startup, `main.py:127-131,206`, so there is no need for lazy resolution), and return `runtime_errors` out of the call rather than accumulating in the rule. If lazy resolution must stay, keep it in a per-request structure, not on the shared compiled rule.

### C-7 — `policies.yaml` is written non-atomically — **fixed**

> **Status: fixed.** The write now goes to a temporary file in the same
> directory, is flushed and `fsync`ed, and is renamed over the target with
> `os.replace`. A reader sees the old file or the new one, never a partial
> one. A failed write removes the temporary file rather than leaving debris.
>
> Two things made this worse than a plain torn-write risk:
>
> - The watcher watches that directory, so the truncation itself could
>   trigger a reload that read the half-written file and surfaced a spurious
>   syntax error mid-save.
> - Comment preservation reads the existing file back, so a file left corrupt
>   by an interrupted write made *every* subsequent save fail with an
>   unhandled 500 — locking the user out of the UI that would have repaired
>   it. An unparseable existing file is now treated as having no comments to
>   preserve.
>
> **R-5 is fixed with it**, because it had to be: an atomic save replaces the
> inode and emits events for the temporary file too, so without filtering,
> every save would trigger extra recompiles. The watcher now filters the
> batch down to the policies file.
>
> `tests/integration/test_policies_atomic_save.py` covers the interaction that
> the fix could plausibly have broken: `PUT /api/policies` does not recompile
> the engine itself, it relies on the watcher, so if the rename had not
> triggered a reload, saving from the UI would have silently stopped taking
> effect.

`policies/writer.py:28-33` truncates the user's file and streams YAML into the open handle. A crash, a full disk, or a container stop mid-write leaves a truncated `policies.yaml`. Worse, the file watcher (`policies/watcher.py:8`) is watching that directory and will fire a reload against the half-written file.

**Fix:** write to a sibling temp file and `os.replace()` — atomic on POSIX, and it means the watcher only ever sees a complete file:

```python
tmp = path.with_suffix(".yaml.tmp")
with tmp.open("w") as f:
    yaml.dump(existing, f)
os.replace(tmp, path)
```

### C-8 — mypy is documented as part of the workflow but never runs, and currently fails — **fixed**

> **Status: fixed.** `uv run mypy src` now runs in `backend.yml` between ruff
> and pytest, so the check the README asks contributors for is the one CI
> enforces.
>
> The single error was a genuine hazard, not a style nit: `rename_pattern_entities`
> bound `e` twice as an `except ... as e` target and then reused it as the loop's
> entity. Python deletes an `except` target at the end of its block, so the name
> was both actively unbound and carrying two meanings in one function. The loop
> variable is now `entity`. Tellingly, the same function already used
> `except Exception as ex` further down — the collision had been worked around
> once locally rather than fixed.
>
> The dead `[tool.pyright]` block is deleted from `pyproject.toml`; pyright reads
> the repo-root `pyrightconfig.json` in preference to it, and the two had already
> drifted (only the root sets `reportMissingImports`). Keeping both meant editing
> two files to exclude the realha fixtures.
>
> Verified by reintroducing the collision: mypy fails, and passes once reverted.
>
> Not done, deliberately: there is still no `[tool.mypy]` section, so mypy runs at
> its lenient defaults. Tightening it is a separate decision from making the
> documented check run at all.

`apps/backend/README.md:90-96` tells contributors to run `uv run mypy src`. `.github/workflows/backend.yml:27-28` runs only `ruff` and `pytest`. mypy is in the dev extras and currently reports:

```
src/home_curator/api/entities.py:435: error: Assignment to variable "e" outside except: block  [misc]
```

`api/entities.py:416,423` bind `except re.error as e`, then line 435 reuses `e` as a loop variable in the same scope. Python deletes the exception target at the end of the `except` block, so this is a genuine readability hazard as well as a type error. Rename the loop variable to `entity`.

There is also duplicate, divergent type-checker configuration: `pyrightconfig.json` at the repo root **and** `[tool.pyright]` in `apps/backend/pyproject.toml:52-57`. Pyright reads the standalone file and ignores the pyproject section when both exist, so the pyproject block is dead config that will drift. Delete one.

**Fix:** add `uv run mypy src` to `.github/workflows/backend.yml`, fix the one error, and delete the redundant pyright config.

---

### C-9 — The addon image had never been built — **fixed**

> Found while trying to build the image for devcontainer work. Because the
> Dockerfile was only exercised on a release tag (P-4) and no release had ever
> been cut, it had never run. It did not work, for three independent reasons:
>
> 1. **`google-re2` could not compile.** `cel-python` depends on it and it
>    publishes no musllinux wheel for any version — confirmed against both PyPI
>    and Home Assistant's own musllinux index — so on Alpine it is always built
>    from source, and the base image has no C++ toolchain. Fixed by adding
>    `g++`, `re2-dev`, `abseil-cpp-dev`, `python3-dev` and `py3-pybind11-dev`
>    as a virtual package removed in the same layer, keeping only the `re2` and
>    `abseil-cpp` runtime libraries.
> 2. **No `.dockerignore`.** The working tree leaked into the build context.
>    Most damaging was the compiled `vite.config.js` — a gitignored artifact of
>    `tsc -b` — which Vite loads in preference to `vite.config.ts`, so the
>    frontend stage built from a stale config and then failed outright against
>    Vite 8. Host `node_modules` were copied over the Linux install too.
> 3. **P-1 confirmed** — `--all-extras` shipped pytest, mypy and ruff into the
>    runtime image.
>
> Two further faults surfaced when testing other architectures: `node:24-alpine`
> publishes no armv7 image, so the frontend stage died before reaching any of
> our code (fixed with `--platform=$BUILDPLATFORM`, which also skips QEMU for
> the entire npm/Vite step); and the runtime base has no armv7 manifest either
> (see P-2).
>
> A new `docker` workflow now builds on every PR touching `apps/` or
> `home-curator/` and asserts the properties that have actually broken: the app
> and its native dependencies import, no dev tooling is present, and
> `index.html` references assets relatively so ingress keeps working.

## 2. Correctness and behaviour

### F-1 — `exceptions_changed` SSE events are published but never consumed

`api/policies.py:85` and `api/exceptions.py:214` publish `{"kind": "exceptions_changed"}`. `api/sse.ts:7` declares it in the `SSEEvent` union. But `hooks/useLiveEvents.ts:14-23` handles `devices_changed`, `policies_changed`, `entities_changed`, `entity_updated` and `entity_deleted` — not `exceptions_changed`. An open Exceptions page in a second tab never refreshes.

```ts
if (e.kind === "exceptions_changed")
  qc.invalidateQueries({ queryKey: ["exceptions-list"] });
```

### F-2 — The Exceptions page cannot filter by entity

`GET /api/exceptions/list` accepts `entity_id` (`api/exceptions.py:111`), but `ListParams` in `hooks/useExceptions.ts:89-96` omits it and `useExceptionsList` never forwards it (`:102-109`). Half of the endpoint's capability is unreachable from the UI — notable given entity exceptions are a first-class concept everywhere else.

### F-3 — Deletion tracking loses its history on restart

`deletion_tracker.py:51-53,62-63` initialises `_last_known_first_seen` to `datetime.now(UTC)` for every device and entity at construction. "First seen" therefore means "first seen since this process booted", and every recorded `DeletionEvent.first_seen_at` is wrong after a restart.

Separately, the reappearance flag lives only in memory (`_state[did] = {STATE_KEY_REAPPEARED: True}`, `:99`), while the DB row is marked reappeared permanently (`mark_reappeared`, `:98`). After a restart the rule stops firing *and* `is_reappearance` won't fire again — the issue vanishes with no user action. Persist `first_seen_at` and the reappeared flag, or document that this rule is best-effort within a single process lifetime.

### F-4 — Dead nav items shipped to users

`components/Layout.tsx:14-15` renders "Automations" and "Areas" as permanently `disabled: true`. There is no Areas page despite `GET /api/areas` existing (`api/areas.py`). Either build them or drop them from `NAV` — greyed-out entries in shipped UI read as breakage.

### F-5 — Devices and Entities pages behave inconsistently

Two user-visible divergences between structurally parallel pages:

| Behaviour | Devices | Entities |
| --- | --- | --- |
| Drawer state | local `useState` (`DevicesPage.tsx:71`) | URL param, deep-linkable (`EntitiesPage.tsx:98`) |
| Stale selection pruning | none | prunes on data change (`EntitiesPage.tsx:200-213`) |

`EntitiesPage.tsx:98` even carries a comment explaining why the URL is the better source of truth — the fix just wasn't applied to Devices. Selecting devices, filtering them out of view, then acting on the selection currently operates on invisible rows.

### F-6b — Sidebar nav items are not real links

`components/Layout.tsx:66-77` renders each nav item as a Mantine `NavLink` with an `onClick` that calls `preventDefault()` then `navigate()`, and **no `href`**. Mantine renders the root as an `<a>`, but an anchor without `href` has no implicit `link` role.

Consequences: screen readers do not announce them as links; keyboard tab order skips them; and middle-click, ⌘-click and "open in new tab" all do nothing. Found while writing the ingress browser tests — `get_by_role("link", …)` could not match them, and the test had to fall back to locating by text.

`pages/Settings/SettingsLayout.tsx:22` *does* set `href`, so the two navs behave differently.

**Fix:** give `NavLink` `component={Link}` and `to=` (React Router's `Link` renders a real anchor with a resolved `href`, and correctly honours the router basename), or at minimum set `href` alongside the existing handler.

### F-6 — Stale comment in `list_entities`

`api/entities.py:137-141` says *"Device + area joins ahead of filtering so sorts on those keys work"*, then does `enriched = list(raw_entities)` with no join. The joins actually happen inline in `_render` and `_device_key`. Delete the comment.

---

## 3. Architecture

### A-1 — `devices.py` and `entities.py` are near-verbatim duplicates

`api/devices.py` (388 lines) and `api/entities.py` (549 lines) share:

- `_matches_query` — identical (`devices.py:67-75`, `entities.py:91-99`)
- `_highest_severity` — identical (`devices.py:78-82`, `entities.py:102-106`)
- `_SEVERITY_RANK` / `_RANK_TO_SEVERITY` — identical (`devices.py:40-41`, `entities.py:43-44`)
- the entire filter → count → sort → paginate → render pipeline, with different field names
- the bulk-action shape: loop, try/except, append `{id, ok, error}` — six times across the two files

The frontend mirrors it: `pages/Devices/` and `pages/Entities/` each have their own `FilterBar`, `PaginationFooter`, `ActionRow` and `filtersFromParams`/`paramsFromFiltersAndPagination`/`cycleSort` (`DevicesPage.tsx:32-102` vs `EntitiesPage.tsx:48-132` — same functions, different field lists).

This is the single biggest maintenance tax in the repo, and it is already producing drift (F-5 is exactly this bug class). The listing endpoints differ only in: the source collection, the filter predicates, the sort key table, and the row renderer.

**Suggested shape** — a generic listing helper parameterised on those four things:

```python
# api/_listing.py
def paginated_listing(items, *, predicates, sort_keys, render, evaluate, ctx, page, page_size, sort_by, sort_dir):
    ...  # filter → count → sort → slice → render
```

and on the frontend, a `useTablePageState({ arrayKeys, boolKeys })` hook that owns URL⇄filter serialisation and sort cycling for both pages. Extract the shared bits before adding a third resource type (Automations and Areas are already on the nav).

### A-2 — `create_app`'s lifespan is a 160-line closure

`main.py:79-239` holds the entire composition root inside one `asynccontextmanager`, including two nested async refresh functions, an event dispatcher, a policy-reload closure, and hand-rolled cleanup duplicated across an `except BaseException` block and a `finally` block (`:214-239`). The duplicated teardown is exactly the kind of thing that drifts — the two blocks already differ in ordering (`session.close()` before vs after `client.stop()`).

**Fix:** extract a `Components` dataclass and a `build_components(settings, client) -> Components` factory, and use `contextlib.AsyncExitStack` so teardown is registered once at acquisition time rather than written out twice.

The import block at `main.py:10-33` — eight separate `from home_curator.api import (x as y)` statements — is a ruff/isort artifact of the aliasing. `from home_curator.api import areas, cache, config_api, devices, ...` collapses it to one line.

### A-3 — `_lazy_app` isn't lazy

```python
# main.py:266-271
# Uvicorn entrypoint — created lazily so test imports don't touch the filesystem.
def _lazy_app() -> FastAPI:
    return create_app()

app = _lazy_app()
```

This is called immediately at import. The *actual* mechanism that keeps imports side-effect-free is the deferral of `Settings()`/`make_engine` into the lifespan (correctly noted at `main.py:81-82`). The wrapper adds nothing and the comment misdescribes it. Replace with `app = create_app()`.

### A-4 — The simulator reaches into rule internals and duplicates the evaluator

`api/policies.py:160,163,218,221` read `rule._when` and `rule._assert` — private, `init=False` fields of `CompiledCustom` (`rules/custom_cel.py:46-47`). It then reimplements the when/assert evaluation loop twice (`_simulate_devices`, `_simulate_entities`), diverging from `CompiledCustom.evaluate` in three ways: no `enabled` check, no exception filtering (intentional, and documented at `:156`), no runtime-error counter.

Any change to `evaluate()` silently fails to reach the simulator, so the preview stops matching reality. Both `rule` parameters are also unannotated (`:139,187`), so mypy checks nothing here.

**Fix:** give `CompiledCustom` a public method that returns a verdict rather than an `Issue` —

```python
def check(self, thing, ctx, *, apply_exceptions: bool = True) -> Verdict:  # matched | passed | failed | errored
```

— and have both `evaluate()` and the simulator call it. That kills the private access, the duplication, and the drift.

### A-5 — Domain types are duplicated across three layers

`EntitySummary` exists as a `TypedDict` in `rules/base.py:10-12` and as a Pydantic model in `api/schemas.py:29-33`. `Severity` is declared three times: `rules/base.py:5`, `policies/schema.py:5`, `api/schemas.py:13`. `Diff` is defined identically in `registry_cache/cache.py:17-21` and `registry_cache/entity_cache.py:14-18`. Consolidate into one module the others import from.

---

## 4. Robustness and performance

### R-1 — `EventBroker` queues are unbounded

`events/broker.py:10` creates `asyncio.Queue()` with no `maxsize`, and `publish` uses `put_nowait` (`:20`). A stalled SSE consumer — a browser tab that stopped reading but hasn't dropped TCP — accumulates events without limit. The SSE handler only notices disconnection every 25 s (`api/events.py:25-28`), so there's a guaranteed window for growth.

**Fix:** `asyncio.Queue(maxsize=100)` and drop-oldest on overflow. These events are notifications, not a log — losing one is harmless because the client refetches on any event.

### R-2 — User-supplied regexes run with no timeout (ReDoS)

Four paths compile and run caller-supplied regex against every device/entity name:

- `api/devices.py:70-72` (`q` with `regex=true`) and `:345` (`rename-pattern`)
- `api/entities.py:95-97` and `:415,422`
- plus `preset: custom` patterns in policies (`rules/naming_convention.py:52-53`)

Python's `re` has no timeout. A catastrophically-backtracking pattern (`(a+)+$`) pins a threadpool worker indefinitely. Exposure is limited — ingress-only, single trusted user — but a stray paste in the search box hangs a worker with no recovery. Consider a length cap on the pattern, or `regex` module with `timeout=`.

### R-3 — Every listing request re-evaluates every rule against every object

`api/devices.py:126-151` and `api/entities.py:143-194` per request: open a DB session, load all acknowledged exception keys, build an `EvaluationContext`, then run every compiled rule against every object — before pagination. On an instance with ~3 000 entities and a handful of CEL rules that's tens of thousands of CEL evaluations per keystroke (the search box debounces at `SEARCH_DEBOUNCE_MS` but still fires per settled keystroke).

Evaluation is only invalidated by: a registry change (already broadcast via SSE), a policy change (already broadcast), or an exception change (already broadcast). That's a well-defined invalidation set, so an issue cache keyed on `(cache_generation, policy_generation, exceptions_generation)` is straightforward and would make listing near-free. Worth doing before this ships to large instances.

### R-4 — SSE disconnect detection lags by up to 25 seconds

`api/events.py:24-32` checks `request.is_disconnected()` only at the top of each loop iteration, and the loop blocks for up to 25 s in `asyncio.wait_for`. Combined with R-1 this means a disconnected client's queue keeps filling for up to 25 s after it's gone. Racing the queue read against a disconnect poll, or letting `EventSourceResponse` handle the ping itself, fixes both.

### R-5 — The policy watcher fires on unrelated files — **fixed**

> Fixed alongside C-7; see there for why it could not be deferred.

`policies/watcher.py:8` watches `path.parent` and reloads on *any* change in `CONFIG_DIR`. Under the add-on that's `/config/home-curator/`, which is currently single-purpose — but an editor swapfile or a future sibling file triggers a full recompile. Filter on the changed path matching `policies_path`.

### R-6 — Exception upsert has a check-then-insert race

`storage/exceptions_repo.py:65-88` does `SELECT` then `INSERT`. The partial unique index prevents duplicate rows, so the failure mode is an `IntegrityError` surfacing as an unhandled 500 rather than a 409. Use SQLite's `INSERT … ON CONFLICT DO UPDATE`.

### R-7 — `delete_device` is documented as non-atomic but the API can't express partial failure

`ha_client/websocket.py:314-320` correctly documents that a multi-config-entry device may be half-unlinked. But `DeleteResult` (`api/schemas.py:192-195`) is `{device_id, ok, error}` — there's no way to say "3 of 4 entries removed, retry is safe". The docstring's guidance ("the caller can surface the error and let the user try again") isn't reachable by the caller. Either add the detail to the result, or state it in the user-facing error string.

---

## 5. Security and least privilege

### S-1 — `map: config:rw` grants full read/write over the HA config directory — **fixed**

> **Status: fixed**, and verified against a real Supervisor rather than by
> inspection. The mapping is now `addon_config` (object form, with `path`
> stated explicitly because the default is documented two different ways), so
> the addon gets its own private directory instead of all of Home Assistant's
> config.
>
> Confirmed in the running addon container: `/config` holds only
> `policies.yaml`, and `secrets.yaml`, `configuration.yaml` and
> `home-assistant_v2.db` are not reachable. The Supervisor's
> `uses deprecated map option 'config'` warning is gone.
>
> `hassio_api: true` is dropped with it (**S-2**) — nothing calls the
> Supervisor API. `homeassistant_api` stays; the websocket client needs it.
>
> No migration was needed: no release has ever been cut, so nobody has data at
> the old location. Doing the like-for-like rename to `homeassistant_config`
> instead would have kept the full blast radius and left this to redo later
> with users' data to move.
>
> Verification also corrected the documentation: the host-side folder is
> `app_configs/` on current Supervisor builds, not `addon_configs/` as I first
> wrote, so the README now describes it rather than hard-coding a name that
> varies by version.

`home-curator/config.yaml:15-16` requests `config:rw` to store one file at `/config/home-curator/policies.yaml`. That grants read/write across the entire HA configuration directory — including `secrets.yaml`, `configuration.yaml` and the HA database.

Home Assistant provides `addon_config:rw`, which maps a private `/addon_configs/<slug>` directory for exactly this case. Switching drops the blast radius to the add-on's own data at the cost of a migration path for existing installs (read the old location if present, write to the new one).

This matters more than usual here because the app evaluates user-authored CEL, writes YAML, and performs bulk destructive operations against the registry.

### S-2 — `hassio_api: true` appears unnecessary

`config.yaml:13-14` requests both `hassio_api` and `homeassistant_api`. The client only ever talks to the HA core websocket (`main.py:94-101`, defaulting to `http://supervisor/core` per `config.py:33`), which is what `homeassistant_api` grants. Nothing in `src/` calls the Supervisor API. Drop `hassio_api` unless there's a planned use.

### S-3 — No API authentication (accepted, but worth stating)

No endpoint authenticates. This is defensible: `config.yaml` exposes no `ports:`, so the only route in is HA ingress, which authenticates upstream. But it is load-bearing and undocumented — anyone who adds a `ports:` mapping for debugging exposes unauthenticated device-delete and entity-rename to the LAN. Add a comment in `config.yaml` and a line in the add-on README recording that ingress is the security boundary.

### S-4 — `assert` used for user-facing error handling

`main.py:91-93` (`assert ha_url is not None`), `config.py:59,64`, `ha_client/websocket.py:189`, `rules/custom_cel.py:56,76`. Assertions are stripped under `python -O` — the config ones would then fail later with a confusing `TypeError` deep in path handling. `apps/backend/README.md:85` documents `assert ha_url is not None` as an *expected user-facing startup error*, which is the clearest sign this should be a real exception with an actionable message.

---

## 6. Packaging and build

### P-1 — The production image ships pytest, mypy and ruff — **fixed**

> Dropped `--all-extras`; verified absent from the built image and asserted in
> the `docker` workflow. See C-9.

`home-curator/Dockerfile:25` runs `uv sync --all-extras --frozen --no-dev`. `--no-dev` excludes dependency *groups*; `dev` here is an optional-dependency **extra** (`pyproject.toml:21-28`), which `--all-extras` explicitly pulls in. The two flags cancel out and the runtime image gets the full test toolchain.

**Fix:** `uv sync --frozen --no-dev` (drop `--all-extras`), or move `dev` from `[project.optional-dependencies]` to `[dependency-groups]`.

### P-2 — Base image pinned in two places, to two different versions — **fixed**

> Worse than described: `release.yml` passes no build-args and never reads
> `build.yaml`, so the pinned `15.0.7` was fiction and the Dockerfile's `ARG`
> default (`20.1.1`) was always used. Since Supervisor 2026.04 no longer passes
> `BUILD_FROM` either, the file was dead twice over. Deleted; the Dockerfile
> `ARG` is now the single source of truth.
>
> This also explained armv7: `base:20.1.1` publishes no armv7 manifest, and the
> newest base that does (`15.0.7`) ships Python 3.11 and lacks `re2-dev`, so it
> can satisfy neither the project's `requires-python` nor `google-re2`. armv7 is
> therefore dropped from `config.yaml` and the release matrix — Home Assistant
> removed all 32-bit architectures in 2025.12 and HAOS 17.0 dropped the armv7
> Raspberry Pi targets, so no supported installation runs it. Pi 4/5 use
> aarch64, which is verified building.

`Dockerfile:1` defaults `BUILD_FROM=ghcr.io/hassio-addons/base:20.1.1`; `build.yaml:2-4` pins `15.0.7` for all three arches. A local `docker build` and a Supervisor build produce different base images — a five-major-version gap. Make `build.yaml` the single source and drop the default, or keep them in sync via a comment referencing the other.

### P-3 — Python version differs across dev, CI and production

| Where | Version |
| --- | --- |
| `pyproject.toml:5` | `>=3.12` |
| `pyrightconfig.json:6` | `3.12` |
| CI (`backend.yml:25`, `frontend.yml:27`, `release.yml:37`) | `3.14` |
| Docker (`Dockerfile:20`) | `apk add python3` — **unpinned** |

The Alpine `python3` package floats with the base image. If it ever resolves below 3.12, `uv sync` fails at image build; if it drifts above what CI tests, production runs an untested interpreter. Pin the interpreter in the Dockerfile and align CI with the version you actually ship.

Node has the same problem in miniature: `package.json:7` says `>=20`, root `README.md:13` says 22, CI and Dockerfile use 24.

### P-4 — The Dockerfile is only exercised at release time — **fixed**

> New `docker` workflow builds and verifies the image on every relevant PR.
> This is the gap that let C-9 go unnoticed indefinitely.

Neither `backend.yml` nor `frontend.yml` builds the image; only `release.yml` (tag push) does. Dockerfile breakage is discovered at the worst possible moment. Add a non-pushing `docker/build-push-action` step with `push: false` for `amd64` on PRs.

### P-5 — Release generates the API client from a backend pointed at a fake HA — **fixed**

> `release.yml` now uses `npm run gen:api:local`, which produces the schema
> in-process. The uvicorn boot, fake credentials and fixed `sleep 5` are gone.

`release.yml:40-46` starts uvicorn with `HA_URL=http://localhost:8123`, `HA_TOKEN=fake`, sleeps 5 s, then scrapes `/openapi.json`. The websocket connect will fail; the app happens to still serve `/openapi.json` because the routes are registered outside the lifespan. It works, but it depends on that and on a fixed 5-second sleep.

`package.json:18` already has `gen:api:local`, which generates the schema in-process with no server at all. Use that in the release workflow and delete the uvicorn dance.

### P-6 — `task setup` doesn't produce a buildable frontend

`src/api/generated.ts` is gitignored (`apps/frontend/.gitignore:5`) and generated. `task setup` (`Taskfile.yml:17-39`) runs `npm install` but never generates it, so immediately after setup `npm run build` fails on the missing module. Tests pass only because esbuild erases type-only imports.

Add `npm run gen:api:local` to `setup:frontend`. Neither the root README's quick-start nor `frontend/README.md` mentions this ordering constraint.

---

## 7. Testing

### T-1 — `task test:backend` fails on a clean checkout

```
task: [test:backend] env -u HA_URL … uv run pytest -q
error: Failed to spawn: `pytest`
  Caused by: No such file or directory (os error 2)
```

`test:backend` assumes `setup:backend` already ran. `uv run` is capable of syncing on demand — either add `deps: [setup:backend]`, or use `uv run --extra dev pytest` so it self-provisions. Minor, but it's the first command a new contributor runs.

### T-2 — Integration tests bypass Alembic

`tests/integration/conftest.py:14-19` builds the schema with `Base.metadata.create_all`. Production builds it with `alembic upgrade head` (`home-curator/run.sh:7`). Nothing asserts the two agree, so a model change without a migration passes the whole suite and breaks on deploy.

`tests/unit/test_alembic_migration.py` verifies migrations run and preserve data, which is good, but it checks a hand-written list of column names (`:27-32`) rather than comparing against the models.

**Fix:** either run migrations in the integration fixture, or add a drift test:

```python
def test_models_match_migrations(tmp_path):
    command.upgrade(_alembic_config(url), "head")
    with create_engine(url).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
```

### T-3 — No coverage gate

`Taskfile.yml:80-94` defines coverage tasks; no workflow runs them and no threshold is enforced. Coverage can regress silently. Add `--cov-fail-under=<current>` to CI and ratchet.

### T-4 — No end-to-end test

Everything is unit or API-level. The ingress bug (C-1) is exactly the class of failure that only a real browser load catches — and `.playwright-mcp/` artifacts show Playwright was used manually during development. One smoke test that loads the built `dist/` through the backend's `StaticFiles` mount and asserts the devices table renders would have caught it.

### T-5 — No frontend linter

There is no ESLint or Prettier config anywhere in the tracked file list. TypeScript `strict` is on with `noUnusedLocals`/`noUnusedParameters` (`tsconfig.json:14-16`), which covers some ground, but nothing catches React hook dependency mistakes — and `EntitiesPage.tsx:200-213` has a `useEffect` that calls `setSelection` with `selection` in its own dependency array, guarded only by a manual `changed` flag. `eslint-plugin-react-hooks` flags this class of thing.

---

## 8. Documentation

### D-1 — The add-on README documents behaviour that doesn't exist — **fixed**

> Fixed while doing C-3: the first-run paragraph now describes what the code
> actually does, and the dead "Settings → Naming Conventions" reference is
> gone. S-1 then corrected the path it points at.

`home-curator/README.md:7`: *"On first start a default `policies.yaml` is created at `/config/home-curator/policies.yaml`."* Nothing writes it (see C-3). It also references *"Settings → Naming Conventions"*, a route that now redirects away (`App.tsx:51-54`).

### D-2 — `CHANGELOG.md` is behind by a whole feature — **fixed**

> **Status: fixed** alongside C-2. Consolidated into a single `0.1.0` entry
> covering the entity work, resync, column visibility and settings
> restructure, and the stale claim that `entities` scope was "reserved for
> future use" is gone. Kept in sync going forward by
> `tests/unit/test_addon_metadata.py`.


`home-curator/CHANGELOG.md` stops at `0.2.0` (dated 2026-04-22). Since then the repo gained the entire Entities view, entity policies, entity bulk actions, the resync button, column visibility, and a settings restructure. The file also states *"Custom policies gain `scope: devices` (required; `entities` reserved for future use)"* — `entities` scope shipped (`policies/schema.py:200`). And no entry matches `config.yaml`'s declared `0.1.0` (see C-2).

### D-3 — `frontend/README.md` describes a different stack — **fixed**

> Now React 19 / TypeScript 6 / Vite 8 / Mantine 9 / Vitest 4, matching
> `package.json`. The layout section gained `pages/Entities/`, the Settings
> description matches its four sub-pages, and the Node claim states what
> `engines` declares and what CI builds on rather than a third number.

| README says (`:16-20`) | Actual (`package.json`) |
| --- | --- |
| React 18 | React 19 |
| TypeScript 5 | TypeScript 6 |
| Vite 5 | Vite 8 |
| Mantine v7 | Mantine v9 |
| Node 22+ (`:55`) | `engines: >=20`, CI uses 24 |

The `Layout` section (`:38-49`) predates `pages/Entities/` and describes Settings as *"Naming Conventions editor"* — it's now four sub-pages.

### D-4 — `backend/README.md` has a stale test count and a documented assertion failure — **fixed**

> Count corrected to 434 and the e2e / real-HA suites documented. `CONFIG_DIR`
> now describes the post-S-1 location. The `assert ha_url is not None`
> troubleshooting entry is **kept deliberately** — it still describes real
> behaviour, because S-4 is open; it is a symptom of that, not of stale docs.

`:29` says *"112 tests"*; there are 381. `:85` documents `assert ha_url is not None` as a troubleshooting entry, which is really a bug report against S-4.

### D-5 — No policy authoring reference — the biggest documentation gap — **fixed**

> `docs/policies.md` covers the file's shape, every rule type with an example,
> the naming presets with their real regexes (including why `title-case` is
> lenient), per-room overrides, the full `device.*` / `entity.*` CEL variable
> tables, worked examples, and the simulator. Every CEL example in it was
> compiled and executed against the real rule engine before publishing.
>
> Linked from the addon README and the root README.

Custom CEL rules are a headline feature. Nothing in the repo documents:

- the `policies.yaml` schema (the source of truth is `policies/schema.py`, unreadable to end users)
- the CEL variables in scope — `device.*` (`rules/base.py:46-65`) and `entity.*` including `entity.device.*` and `entity._state.*` (`:97-127`)
- what `_state` contains (currently just `reappeared_after_delete`)
- the built-in preset regexes (`rules/naming_convention.py:19-46`) — the `title-case` pattern in particular has a dozen carefully-chosen edge cases documented only as a code comment
- worked examples

A user hitting the CEL editor has no reference. This is the highest-value doc to write.

### D-6 — No LICENSE — **fixed**

> MIT, at the owner's choice.

There is no LICENSE file. `repository.yaml` publishes this as an installable HA add-on repository — users have no terms. Add one.

### D-6b — Errors in `docs/architecture/` — **fixed**

> `live-updates.md`'s `POST /api/resync` corrected to `/api/cache/resync`. The
> two `frontend.md` errors were fixed earlier, with C-1.

Spotted while updating those diagrams for the ingress fix:

- `live-updates.md:103` documents the manual resync endpoint as `POST /api/resync`. The actual route is `POST /api/cache/resync` (`api/cache.py:6,10`). **Still outstanding.**
- `frontend.md` stated that `generated.ts` "is committed: CI typechecks without booting the backend". It is gitignored (`apps/frontend/.gitignore:5`); what actually makes CI work is `npm run typecheck` running `gen:api:local` first. **Fixed** as part of C-1.
- `frontend.md` described `baseUrl` resolving to `window.location.origin` as correct in all environments — it documented the C-1 bug as intended behaviour. **Fixed.**

Worth a pass over the rest of these diagrams against the code; they were written quickly and at least three claims in two files were wrong.

### D-7 — `docs/` is gitignored but three files are tracked anyway — **fixed**

> The three `docs/superpowers/plans/` files are untracked. `docs/` itself is
> not ignored — only `docs/superpowers/` — so `docs/architecture/` and the new
> `docs/policies.md` are unaffected.

`.gitignore:2` ignores `docs/superpowers/`, yet three plan files are tracked (`docs/superpowers/plans/2026-04-24-backend-{pyright,ruff,test-warning}-cleanup.md`) — added before the ignore rule and never removed. Either untrack them or narrow the ignore. Right now `docs/` contains only stale artifacts and no user-facing documentation.

### D-8 — Missing repo hygiene files

No `CONTRIBUTING.md`, no issue/PR templates, no `SECURITY.md`. `CLAUDE.md` encodes the working style but is agent-facing. For a public add-on repo, a short CONTRIBUTING that states the `task setup` → `task test` → PR-to-main loop would carry most of the value.

### D-9 — Taskfile is missing the tasks the docs reference — **fixed**

> Added `task lint` (ruff + mypy + tsc), `task lint:backend`, and `task check`
> (lint plus both test suites). The backend README now points at them instead
> of listing raw commands.

`apps/backend/README.md:90-96` tells you to `cd apps/backend && uv run ruff check src tests && uv run mypy src`. There is no `task lint` or `task check`. `CLAUDE.md:15` says *"Add Taskfile tasks when they aid local development or repeated operations"* — lint and typecheck qualify. Also missing: `task build`, `task docker:build`.

```yaml
lint:
  desc: Lint + typecheck everything
  cmds:
    - task: lint:backend
    - task: typecheck

lint:backend:
  dir: "{{.BACKEND_DIR}}"
  cmds:
    - uv run ruff check src tests
    - uv run mypy src
```

---

## 9. Suggested order of work

**Before the next release** — these are user-visible breakage:

1. C-1 ingress paths (the add-on does not work as packaged)
2. C-2 release tag / version sync
3. C-3 create `CONFIG_DIR`, and reconcile the README's first-run claim
4. C-8 fix the mypy error, add mypy to CI
5. P-1 stop shipping the test toolchain in the runtime image

**Next** — correctness and safety:

6. C-4 exceptions area filter, and the `bulk_delete` return value
7. C-7 atomic policy writes
8. C-6 make rule evaluation pure
9. C-5 `Settings` on `AppState`
10. F-1 wire up `exceptions_changed`
11. S-1 move to `addon_config:rw`

**Then** — the structural work that stops the drift:

12. A-1 extract the shared listing pipeline (backend and frontend)
13. A-4 give `CompiledCustom` a public verdict method
14. A-2 restructure the lifespan
15. R-3 cache issue evaluation

**Ongoing** — docs and tooling:

16. D-5 policy authoring reference
17. D-1 to D-4 correct the stale READMEs and CHANGELOG
18. D-6 LICENSE
19. T-2 migration drift test; T-5 ESLint; P-4 Docker build on PRs

---

## What's good

Worth recording, because a review that only lists problems misrepresents the codebase:

- **Comment quality is unusually high.** Comments explain *why*, not *what* — `entities.py:46-49` on the sentinel choice, `naming_convention.py:22-37` on the title-case edge cases, `websocket.py:45-47` on the ping timeouts, `EntitiesPage.tsx:93-97` on the drawer state race. This is the kind of context that's normally lost.
- **Test coverage is broad and well-organised.** 381 backend tests split cleanly into unit and integration, with a `FakeHAClient` that makes the whole API testable with no external dependency. 159 frontend tests including hooks and modals.
- **Type discipline is strong.** Pydantic validation at the HA boundary (`websocket.py:285-287`), a typed client generated from the live OpenAPI spec, TS `strict` with unused-locals checks.
- **The rule engine's extension model is clean.** Adding a policy type means a schema class, a compiler, and one `elif` in `RuleEngine.compile` — the `CompiledPolicy` protocol keeps the engine ignorant of specifics.
- **Failure handling in the websocket client is genuinely thought through** — reconnect backoff, failing in-flight futures on disconnect (`websocket.py:162-163`), re-subscribing on reconnect, and a `reconnected` event so caches refresh.
- **Bulk operations return per-item results** rather than failing the batch, and destructive operations offer dry-run previews.
