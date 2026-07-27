# Data model

Two distinct model layers, deliberately not shared:

1. **Persisted rows** — SQLAlchemy, in `storage/models.py`. Home Curator owns these.
2. **In-flight domain objects** — Pydantic at the HA boundary (`ha_client/models.py`), converted to dataclasses for rule evaluation (`rules/base.py`). HA owns the underlying truth; nothing here is persisted.

## Persisted schema

```mermaid
erDiagram
    exceptions {
        int id PK
        string device_id "nullable"
        string entity_id "nullable"
        string policy_id
        datetime acknowledged_at
        string acknowledged_by "nullable"
        string note "nullable"
    }

    deletion_events {
        int id PK
        string device_id "nullable, indexed"
        string entity_id "nullable, indexed"
        string platform "nullable"
        string identifiers_hash "indexed"
        datetime first_seen_at
        datetime deleted_at
        datetime reappeared_at "nullable"
    }

    entity_roles {
        int id PK
        string device_id
        string role "battery | connectivity"
        string entity_id
    }
```

No foreign keys between these tables — every one of them points at a Home Assistant id that lives outside the database, so referential integrity is enforced by HA, not SQLite. What the schema *does* enforce:

| Constraint | Table | Meaning |
| --- | --- | --- |
| `ck_exceptions_target_exactly_one` | `exceptions` | `(device_id IS NULL) <> (entity_id IS NULL)` — a row targets a device **or** an entity, never both, never neither |
| partial unique index (Alembic) | `exceptions` | unique on `(COALESCE(device_id,''), COALESCE(entity_id,''), policy_id)` — one acknowledgement per target+policy |
| `ck_deletion_target_exactly_one` | `deletion_events` | same discriminated-target rule |
| `uq_entity_roles_device_role` | `entity_roles` | one battery entity and one connectivity entity per device |

`identifiers_hash` is what makes reappearance detection work across id churn. For devices it hashes the HA `identifiers` tuples; for entities it hashes `(platform, unique_id)`, falling back to `(platform, entity_id)` when the entity has no `unique_id`. A user-renamed entity keeps its identity; a re-paired device keeps its identity. Timestamps are stored via the `TZDateTime` type decorator so they round-trip as timezone-aware UTC through SQLite.

## HA boundary → rule-engine shapes

```mermaid
classDiagram
    direction LR

    class HADevice {
        <<pydantic, frozen, extra=ignore>>
        +id str
        +name str?
        +name_by_user str?
        +manufacturer str?
        +model str?
        +area_id str?
        +integration str?
        +disabled_by str?
        +identifiers list~list~str~~
        +config_entries list~str~
        +entities list~HADeviceEntityRef~
        +created_at str?
        +modified_at str?
    }

    class HAEntity {
        <<pydantic, frozen, extra=ignore>>
        +entity_id str
        +name str?
        +original_name str?
        +icon str?
        +platform str
        +device_id str?
        +area_id str?
        +disabled_by str?
        +hidden_by str?
        +unique_id str?
    }

    class HAArea {
        <<pydantic, frozen>>
        +id str
        +name str
    }

    class Device {
        <<dataclass, mutable>>
        +id str
        +name str
        +name_by_user str?
        +area_id str?
        +area_name str?
        +integration str?
        +disabled_by str?
        +entities list~EntitySummary~
        +state dict
        +display_name() str
        +to_cel_context() dict
    }

    class Entity {
        <<dataclass, mutable>>
        +entity_id str
        +name str?
        +original_name str?
        +domain str
        +platform str
        +device_id str?
        +area_id str?
        +area_name str?
        +hidden_by str?
        +unique_id str?
        +state dict
        +display_name() str
        +to_cel_context(device_context, area_name) dict
    }

    class Area {
        <<dataclass, frozen>>
        +id str
        +name str
    }

    HADevice ..> Device : _to_device(area_lookup)
    HAEntity ..> Entity : _to_entity(area_lookup, device_lookup)
    HAArea ..> Area : RegistryCache._load_unlocked
    HADevice o-- HADeviceEntityRef
    Device o-- EntitySummary
```

The conversion is where enrichment happens, and it carries three decisions worth knowing:

- **`area_name` is resolved at conversion time**, so rules never need the area map to render a message. For an entity, the *name* comes from the effective area (its own `area_id`, else the owning device's), but the stored **`area_id` stays the entity's own override** — otherwise `entity_missing_area` in strict mode could never fire.
- **`state` is a computed side-channel**, empty on construction and populated by `DeletionTracker` (e.g. `reappeared: True`). CEL policies see it under the key `_state` so expressions can tell computed fields apart from HA's own attributes.
- **`Device` and `Entity` are mutable**, unlike everything on the HA side. That is why `RegistryCache.refresh()` deep-copies the before-snapshot: a later mutation of `entities` or `state` would otherwise corrupt the diff it is comparing against.

Read models use `extra="ignore"` so a new HA field never raises; patch models (`HADeviceUpdate`, `HAEntityUpdate`) use `extra="forbid"` so a caller typo fails loudly instead of silently updating nothing.
