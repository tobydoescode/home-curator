# Rule engine

The one place in the backend with genuine polymorphism. A YAML policy is parsed into a validated Pydantic model, *compiled* into a dataclass that satisfies the `CompiledPolicy` protocol, and then evaluated against every `Device` or `Entity`.

Parse and compile are separate on purpose: schema validation catches malformed config at load, while compilation catches things only knowable later (a bad CEL expression, an override naming an area that doesn't exist). A compile failure is recorded on the rule as `compile_error` rather than raised, so one broken rule cannot take down the other five.

## Compiled policies

```mermaid
classDiagram
    direction TB

    class CompiledPolicy {
        <<interface>>
        +id str
        +enabled bool
        +severity Severity
        +rule_type str
        +scope TargetScope
        +compile_error str?
        +evaluate(thing, ctx) Issue?
    }

    class CompiledMissingArea {
        +rule_type = "missing_area"
        +scope = "devices"
    }
    class CompiledEntityMissingArea {
        +require_own_area bool
        +rule_type = "entity_missing_area"
        +scope = "entities"
    }
    class CompiledNamingConvention {
        +overrides list~_OverrideEntry~
        +rule_type = "naming_convention"
        +scope = "devices"
    }
    class CompiledEntityNaming {
        +name _NameCompiled
        +entity_id _EntityIdCompiled
        +rule_type = "entity_naming_convention"
        +scope = "entities"
    }
    class CompiledReappeared {
        +rule_type = "reappeared_after_delete"
        +scope "devices or entities"
    }
    class CompiledCustom {
        +when_ CEL
        +assert_ CEL
        +message str
        +rule_type = "custom"
        +scope "devices or entities"
    }

    CompiledPolicy <|.. CompiledMissingArea
    CompiledPolicy <|.. CompiledEntityMissingArea
    CompiledPolicy <|.. CompiledNamingConvention
    CompiledPolicy <|.. CompiledEntityNaming
    CompiledPolicy <|.. CompiledReappeared
    CompiledPolicy <|.. CompiledCustom

    class _OverrideEntry {
        <<private helper>>
    }
    class _NameCompiled {
        <<private helper>>
    }
    class _EntityIdCompiled {
        <<private helper>>
    }

    CompiledNamingConvention *-- _OverrideEntry
    CompiledEntityNaming *-- _NameCompiled
    CompiledEntityNaming *-- _EntityIdCompiled
```

`CompiledPolicy` is a `runtime_checkable` `Protocol`, so none of these six declare it as a base class — they satisfy it structurally. `rule_type` and `scope` are plain dataclass fields with defaults, not properties, which is why they show as `= "value"` above.

`scope` is fixed for four rules and configurable for two. `reappeared_after_delete` takes its scope from the policy (defaulting to `devices`, preserving pre-entity configs) and `custom` takes it from `CustomPolicy.scope`.

## Schema → compiled

```mermaid
flowchart TB
    Yaml[("policies.yaml")] -->|"load_policies_file"| Load{"valid?"}
    Load -->|no| Err["LoadResult(file=None, error=...)<br/><i>last-good rules stay loaded</i>"]
    Load -->|yes| Merge["_merge_missing_baselines<br/><i>append baseline ids not present</i>"]
    Merge --> PF["PoliciesFile(version=1, policies)"]
    PF -->|"discriminated on <code>type</code>"| Union

    subgraph Union["Policy union"]
        MA["MissingAreaPolicy"]
        EMA["EntityMissingAreaPolicy"]
        NC["NamingConventionPolicy"]
        ENC["EntityNamingConventionPolicy"]
        RAD["ReappearedAfterDeletePolicy"]
        CP["CustomPolicy"]
    end

    MA -->|compile_missing_area| C1["CompiledMissingArea"]
    EMA -->|compile_entity_missing_area| C2["CompiledEntityMissingArea"]
    NC -->|"compile_naming_convention(p, ctx)"| C3["CompiledNamingConvention"]
    ENC -->|"compile_entity_naming(p, ctx)"| C4["CompiledEntityNaming"]
    RAD -->|compile_reappeared| C5["CompiledReappeared"]
    CP -->|compile_custom| C6["CompiledCustom"]

    C1 & C2 & C3 & C4 & C5 & C6 --> RE["RuleEngine.compiled"]
```

`RuleEngine.compile` dispatches on `isinstance` and raises `TypeError` on an unhandled policy type — adding a seventh policy without a compile branch fails loudly at startup rather than silently skipping.

The two naming compilers take `ctx` because room overrides may reference an area by *name*; they resolve it to an `area_id` at compile time so evaluation is a dict lookup.

## Evaluation

```mermaid
sequenceDiagram
    participant API as "api/devices.py"
    participant RE as RuleEngine
    participant R as CompiledPolicy
    participant Ctx as EvaluationContext

    API->>RE: evaluate(thing, ctx)
    RE->>RE: scope = "entities" if isinstance(thing, Entity) else "devices"
    loop each compiled rule
        alt rule.compile_error is not None
            RE-->>RE: skip (broken rule)
        else rule.scope != scope
            RE-->>RE: skip (not applicable)
        else
            RE->>R: evaluate(thing, ctx)
            R->>Ctx: ("device", id, policy_id) in exceptions?
            alt acknowledged
                R-->>RE: None
            else violated
                R-->>RE: Issue(policy_id, rule_type, severity,<br/>message, target_kind, target_id)
            end
        end
    end
    RE-->>API: list[Issue]
```

Three filters run in order, and the ordering matters: broken rules are skipped before scope, scope before evaluation, and the per-rule `enabled` check happens inside `evaluate` (so a disabled rule still counts as compiled and is still reported by `compile_errors()`).

`EvaluationContext.exceptions` is a set of **3-tuples** `(target_kind, target_id, policy_id)`. The `target_kind` discriminator is what lets a device and an entity share an id without their acknowledgements colliding. `Issue` mirrors that shape with `target_kind` + `target_id`, so downstream consumers route an issue without inferring its kind from `rule_type`.

`EvaluationContext.devices_by_id` is only populated for entity-scope rules that need the owning device — `custom_cel` (to build `entity.device` context) and `entity_missing_area` in lenient mode. It defaults to empty so device-only callers need not supply it.

## Reload

`policies/watcher.py` watches the *parent directory* via `watchfiles.awatch` (editors write-and-rename, so watching the file alone misses changes). On change, `reload_policies` re-reads, rebuilds `EvaluationContext` from a fresh session, recompiles, and publishes `policies_changed`. If the new file is invalid, `policies_error` is set and **the previously compiled rules stay live** — a typo in the editor never blanks the UI's issue list.
