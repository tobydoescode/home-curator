# Tech Debt

Running list of known debts / follow-ups. Each entry has context + a suggested
shape so it can be picked up independently.

---

## HAClient TypedDict modelling

**Status:** Partial fix applied 2026-04-23 on `feature/entities-1-backend-foundation`.
**Follow-up:** Full rethink still outstanding.

### Background

`HADeviceDict` and `HAEntityDict` in `apps/backend/src/home_curator/ha_client/base.py`
are declared `TypedDict, total=False` so the client can tolerate HA payloads
that omit optional fields (older HA versions, test fixtures, etc.). With
`total=False`, Pyright's `reportTypedDictNotRequiredAccess` flags every
subscript access (`d["id"]`, `e["entity_id"]`, etc.) as potentially unsafe —
even though our code only operates on values we just put into the dict.

### What we did (partial fix)

- Marked the always-present keys as `Required[str]`:
  - `HADeviceDict.id`
  - `HAEntityDict.entity_id`
- Added `# type: ignore[typeddict-item]` on the two `.update()` call sites in
  `FakeHAClient` and on three test-side subscript accesses to keys that are
  legitimately `total=False` but test fixtures guarantee.

This dropped Pyright errors in the feature worktree from 14 → 0.

### What's still owed

The broader problem: these `TypedDict`s leak `total=False`-style uncertainty
into every consumer. Better long-term options:

1. **Dataclasses + constructor-level validation.** Replace `HADeviceDict` /
   `HAEntityDict` with frozen dataclasses that validate at ingest boundary
   (`WebSocketHAClient.get_devices` / `.get_entities`). Consumers get clean
   attribute access; test fixtures construct via kwargs. Costs: rewriting
   every `d["id"]` site (~6 files) and fixture shape changes in ~5 tests.

2. **`NotRequired[...]` everywhere, keep TypedDict.** Flip the default: drop
   `total=False`, mark each optional key with `NotRequired[str | None]`.
   Required keys (`id`, `entity_id`) work without annotation. Smaller change
   than option 1 but still churns every field. Consumers keep the dict
   shape they already use.

3. **Split required/optional halves.** Declare a base `_HADeviceReq(TypedDict)`
   (required keys, `total=True`) and extend it with `HADeviceDict(_HADeviceReq,
   total=False)` for optional keys. Works today without `Required[...]`;
   slightly verbose. Two classes per HA type.

Recommendation: option 2 (`NotRequired` everywhere). Cleanest static surface
without dataclass-sized churn. Do this *after* the Entities view ships, so we
don't re-migrate fields mid-feature.

### Why IDE diagnostics lag

While this debt exists across the branch tree, editors running Pyright see
errors on **any worktree** whose files reference types that haven't been
updated in the checked-out main branch. Diagnostics will self-clear once
whichever branch ships the fix lands on main.
