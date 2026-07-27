# Changelog

## 0.1.0

First release.

### Devices

- Devices view with search (plain or regex), filtering by room, issue type and
  integration, multi-select, sortable columns, pagination and live SSE updates.
- Bulk actions: assign room, rename, and regex rename-pattern with a dry-run
  preview.
- Edit drawer for a single device, and delete (single and bulk) with
  per-device results so a partial failure reports which devices failed.

### Entities

- Entities view mirroring Devices, with additional filtering by domain and by
  disabled / hidden state, and a device column joined from the device registry.
- Bulk actions: assign room, enable / disable, show / hide, delete, and a
  dual-regex rename covering both `entity_id` and friendly name, with dry-run.
- Edit drawer for a single entity, including `entity_id` rename.
- Deep-linkable: `?entity=<id>` opens the drawer directly.

### Policies

- Built-in rules: missing room, naming convention (global plus per-room
  overrides, with a `starts_with_room` modifier), and reappeared-after-delete.
- Entity-scope rules: entity naming convention (separate friendly-name and
  `entity_id` blocks) and entity missing area, with a lenient mode that accepts
  the owning device's area.
- Custom rules via CEL expressions, scoped to devices or entities, authored in
  the UI with debounced compile validation and a simulator that groups results
  into failing, errored and passing.
- Policies are hot-reloaded from `policies.yaml`; invalid content keeps the
  last-good rules loaded and surfaces the error in the UI.
- Baseline policies are merged in on load, so a config file written by an
  earlier version still gains newly-added built-in rules.

### Exceptions

- Acknowledge an issue per device or per entity, with an optional note.
- Exceptions page listing every acknowledgement, with filtering, pagination and
  bulk delete.
- Removing a policy cascades: exceptions referencing it are deleted
  automatically.

### Interface

- Settings split into Device Settings, Entity Settings, Global Policies and
  Exceptions.
- Per-table column visibility, persisted locally.
- Manual resync button for when the cache looks stale, light/dark colour scheme
  toggle, and a live indicator showing when the last registry event arrived.
