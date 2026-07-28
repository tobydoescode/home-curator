# Writing policies

Home Curator decides what counts as "untidy" from a single file,
`policies.yaml`. Everything in it is editable from **Settings** in the UI; this
page is the reference for editing it by hand.

- **In the add-on:** `/config/policies.yaml` inside the container. On the host
  it is in Home Assistant's per-addon config folder, reachable with the File
  Editor or Samba add-ons. That folder is the add-on's own — it has no access
  to Home Assistant's `configuration.yaml`, `secrets.yaml` or database.
- **In development:** `apps/backend/.dev-config/home-curator/policies.yaml`.

The file is re-read about a second after you save it. If it does not parse or
does not validate, the last good version stays loaded and the error is shown in
the UI — a broken edit degrades the app, it does not take it down.

## Shape

```yaml
version: 1
policies:
  - id: missing-room
    type: missing_area
    enabled: true
    severity: warning
```

`version` must be `1`. Every policy has these four fields:

| Field | Required | Notes |
| --- | --- | --- |
| `id` | yes | Unique, non-empty. Used to acknowledge exceptions, so renaming an id orphans its acknowledgements — they are deleted on save. |
| `type` | yes | One of the rule types below. |
| `enabled` | no | Defaults to `true`. |
| `severity` | yes | `info`, `warning` or `error`. Only affects presentation and sorting. |

Unknown keys are rejected rather than ignored, so a typo fails loudly instead
of silently doing nothing.

## Rule types

### `missing_area` — devices with no room

```yaml
- id: missing-room
  type: missing_area
  enabled: true
  severity: warning
```

Flags any device whose `area_id` is unset.

### `entity_missing_area` — entities with no room

```yaml
- id: entity-missing-area
  type: entity_missing_area
  enabled: false
  severity: info
  require_own_area: false
```

An entity usually inherits its area from the device that owns it. By default
that counts, so only genuinely unassigned entities are flagged. Set
`require_own_area: true` to demand an area on the entity itself and flag ones
that only inherit.

### `reappeared_after_delete` — things that came back

```yaml
- id: reappeared
  type: reappeared_after_delete
  enabled: true
  severity: info
  scope: devices        # or: entities
```

Flags a device or entity that was deleted and has since returned — usually an
integration recreating something you removed on purpose.

Identity is tracked by Home Assistant's device identifiers, and for entities by
`(platform, unique_id)` so that renaming an entity does not look like a new
one. Entities with no `unique_id` fall back to `(platform, entity_id)`, which a
rename does defeat.

### `naming_convention` — device names

```yaml
- id: naming-convention
  type: naming_convention
  enabled: true
  severity: warning
  global:
    preset: snake_case
  starts_with_room: false
  rooms: []
```

Checks each device's display name — the user override if set, otherwise the
integration's name.

`starts_with_room: true` additionally requires the name to begin with its
room, formatted to match the preset (`Living Room` → `living_room_` for
snake_case, `living-room-` for kebab-case).

### `entity_naming_convention` — entity names and ids

```yaml
- id: entity-naming-convention
  type: entity_naming_convention
  enabled: true
  severity: warning
  name:
    global:
      preset: title-case
    starts_with_room: false
    rooms: []
  entity_id:
    starts_with_room: false
    rooms: []
```

Two independent checks. `name` works exactly like `naming_convention` above,
against the entity's friendly name.

`entity_id` checks the slug. Its convention is **fixed to snake_case** and
`preset`/`pattern` are rejected there — entity ids are machine-facing, so
allowing per-room formats would be a trap rather than a feature. Rooms may only
opt out entirely:

```yaml
  entity_id:
    rooms:
      - room: Garage
        enabled: false
```

### `custom` — your own rule, in CEL

```yaml
- id: hue-devices-need-a-model
  type: custom
  enabled: true
  severity: warning
  scope: devices          # or: entities
  when: 'device.integration == "hue"'
  assert: 'device.model != ""'
  message: Hue devices should record a model
```

`when` selects what the rule applies to (defaults to everything). `assert` is
what must be **true** for that thing to be considered tidy — when it is false,
`message` is reported. Both are [CEL](https://github.com/google/cel-spec)
expressions.

A rule that fails to compile is reported in the UI and skipped; it does not
stop the other rules running. An expression that throws at runtime — a typo in
a field name, say — is treated as "no issue" for that one device rather than
failing the whole page.

## Naming presets

Patterns are compiled with [RE2](https://github.com/google/re2), not Python's
`re`. RE2 cannot backtrack, so no pattern can hang the add-on — but it also
has no lookahead, lookbehind or backreferences, since those are what make
backtracking necessary. A pattern using them is rejected with an explanation
rather than accepted and occasionally taking minutes. Everything else behaves
identically.

| Preset | Matches | Examples |
| --- | --- | --- |
| `snake_case` | `^[a-z0-9]+(_[a-z0-9]+)*$` | `living_room_lamp` |
| `kebab-case` | `^[a-z0-9]+(-[a-z0-9]+)*$` | `living-room-lamp` |
| `title-case` | (see below) | `Living Room Lamp` |
| `prefix-type-n` | `^[a-z]+_[a-z]+_[0-9]+$` | `garage_light_1` |
| `custom` | your own `pattern` | — |

`custom` requires a `pattern`, and the other presets reject one:

```yaml
  global:
    preset: custom
    pattern: '^[A-Z]{3}-[0-9]+$'
```

`title-case` is deliberately lenient about real-world English, and accepts:
apostrophes (`Clara's`), hyphenated words (`En-Suite`), acronyms (`AP`,
`ESPresense`), trailing numbers (`Side Lamp 2`), digit-led abbreviations *after* the first
word (`Printer 3D`, `Sensor 12V` — but not `3D Printer`, since a name may not
begin with a digit), lowercase function words after the first word
(`Mum and Dad's Bedroom`), and a trailing parenthesised note (`Hub (Local)`).
It deliberately still rejects names carrying a MAC address, because colons are
excluded from that trailing group.

## Per-room overrides

Any naming block takes a `rooms` list. Each entry identifies a room by `room`
(its Home Assistant area name, case-insensitive) or by `area_id`, and then
either changes the convention or turns it off:

```yaml
  rooms:
    - room: Garage
      preset: prefix-type-n
    - room: Loft
      enabled: false            # no naming check in here at all
    - area_id: kitchen_abc123
      preset: custom
      pattern: '^K-[0-9]+$'
      starts_with_room: true
```

A room may appear only once per block; duplicates are rejected rather than
silently shadowing each other.

Overrides are matched by **name**, so an override naming a room that does not
exist yet is reported as a compile error. Creating that area in Home Assistant
clears it automatically — no restart needed.

## CEL variables

### `scope: devices` — `device`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Home Assistant device id |
| `name` | string | The integration's name |
| `name_by_user` | string / null | The user's override, if any |
| `manufacturer` | string / null | |
| `model` | string / null | |
| `area_id` | string / null | |
| `area_name` | string / null | Resolved room name |
| `integration` | string / null | e.g. `hue`, `zwave_js` |
| `disabled_by` | string / null | |
| `entities` | list | Each `{id, domain}` |
| `_state` | map | Computed flags — see below |

### `scope: entities` — `entity`

| Field | Type | Notes |
| --- | --- | --- |
| `entity_id` | string | e.g. `light.kitchen` |
| `name` | string / null | The user's override, if any |
| `original_name` | string / null | The integration's name |
| `domain` | string | e.g. `light` |
| `platform` | string | Providing integration |
| `device_id` | string / null | |
| `area_id` | string / null | The entity's **own** area, null when inherited |
| `area_name` | string / null | The **effective** room, including inherited |
| `disabled_by` | string / null | |
| `hidden_by` | string / null | |
| `icon` | string / null | |
| `device` | map / null | The owning device, same shape as above |
| `_state` | map | Computed flags — see below |

`_state` holds values Home Curator computes rather than reads from Home
Assistant. Currently one: `reappeared_after_delete`, true when this thing was
deleted and has come back.

Note the asymmetry on entities: `area_id` is the override and is null for an
entity that inherits its room, while `area_name` is always the effective room.
For "is this in the kitchen", use `area_name`.

### Examples

Every device from a given integration must have a model recorded:

```yaml
- id: zwave-model-required
  type: custom
  scope: devices
  severity: warning
  when: 'device.integration == "zwave_js"'
  assert: 'device.model != null && device.model != ""'
  message: Z-Wave devices should record a model
```

Nothing may be named after its MAC address:

```yaml
- id: no-mac-addresses
  type: custom
  scope: devices
  severity: error
  assert: '!device.name.matches(".*[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}.*")'
  message: Name looks like a MAC address
```

Lights must not be left in the same room as their device by accident — flag
entities whose own area disagrees with their device's:

```yaml
- id: entity-area-differs-from-device
  type: custom
  scope: entities
  severity: info
  when: 'entity.device != null && entity.area_id != null'
  assert: 'entity.area_id == entity.device.area_id'
  message: Entity is in a different room from its device
```

Anything that reappeared after being deleted, as an error rather than the
built-in rule's info:

```yaml
- id: reappeared-is-serious
  type: custom
  scope: devices
  severity: error
  assert: '!has(device._state.reappeared_after_delete)'
  message: This device came back after being deleted
```

## Testing a rule before saving

**Settings → Global Policies** compiles as you type and runs the rule against
your real devices or entities, grouping the results into failing, passing and
errored. Errored means the expression threw — usually a field that does not
exist on that particular thing.

The simulator deliberately ignores acknowledged exceptions, so you see the raw
effect of the rule.

## Built-in defaults

A fresh install is seeded with six policies: `naming-convention`,
`missing-room` and `reappeared` enabled for devices, plus
`entity-naming-convention` enabled and `entity-missing-area` /
`entity-reappeared` disabled for entities.

Upgrades never overwrite your file. New built-in rules added by a later version
are merged in on load if their id is absent, keeping your `enabled` and
`severity` choices for everything already there.
