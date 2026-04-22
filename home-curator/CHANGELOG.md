## 0.2.0 — 2026-04-22

### Breaking
- The canned policy type `name_starts_with_room` has been removed. Its behaviour is now a modifier toggle inside `naming_convention` (`starts_with_room: true`). Files that still reference `name_starts_with_room` will fail to load; edit `/config/home-curator/policies.yaml` by hand to remove the standalone policy and set `starts_with_room: true` on the naming convention instead.

### Added
- Settings area split into Device Settings, Entity Settings (placeholder), Global Policies (custom CEL rules + live simulator), and Exceptions.
- Per-room overrides can now set Preset = "Disabled" to opt a room out of the naming policy entirely.
- Room overrides use a real HA-area picker instead of free-text.
- Custom CEL rules are authorable in the UI with multiline editors, debounced compile validation, and a grouped failing/errored/passing results simulator.
- Exceptions page lists all acknowledged exceptions with single and bulk delete.

### Changed
- `GET /api/exceptions/list` returns a paginated, filterable, joined response (legacy `GET /api/exceptions?device_id=…` is unchanged).
- `PUT /api/policies` now cascades: orphan exceptions (referencing a policy that no longer exists) are deleted automatically.
- `naming_convention` policies gain `starts_with_room: bool` and per-room overrides gain `enabled: bool`.
- Custom policies gain `scope: devices` (required; `entities` reserved for future use).

### API
- New: `GET /api/policies/file`, `POST /api/policies/compile`, `POST /api/policies/simulate`, `GET /api/areas`, `GET /api/exceptions/list`, `POST /api/exceptions/bulk-delete`.

## 0.1.0

- Initial release.
- Devices view with search, filtering, selection, pagination, and live SSE updates.
- Built-in rules: missing room, naming convention (global + per-room), reappeared-after-delete.
- Custom rules via CEL expressions.
- Bulk actions: assign room, rename, rename-pattern (with dry-run preview).
- Exception acknowledgement per device.
- Settings UI for naming conventions.
