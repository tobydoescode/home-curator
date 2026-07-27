# Live updates

How a change in Home Assistant reaches the browser, and how a change made in the browser gets back.

## The HA client seam

```mermaid
classDiagram
    direction LR

    class HAClient {
        <<interface>>
        +start() async
        +stop() async
        +get_devices() list~HADevice~
        +get_areas() list~HAArea~
        +get_entities() list~HAEntity~
        +update_device(device_id, HADeviceUpdate) async
        +delete_device(device_id) async
        +update_entity(entity_id, HAEntityUpdate) async
        +delete_entity(entity_id) async
        +subscribe(handler) unsubscribe
    }

    class WebSocketHAClient {
        +url str
        +token str
        -reconnect with backoff
    }

    class FakeHAClient {
        <<test double>>
        -in-memory registries
    }

    HAClient <|.. WebSocketHAClient
    HAClient <|.. FakeHAClient
```

This is the seam that makes the backend testable. `create_app(ha_client=...)` takes an injected client, so the entire integration suite runs against `FakeHAClient` with no HA instance and no network.

`subscribe` returns its own unsubscribe closure rather than exposing an `unsubscribe(handler)` method — the caller cannot leak a subscription by losing the handler reference, and `main.py`'s lifespan just calls `unsub()` on teardown.

## Events

`HAEvent` is a Pydantic discriminated union on `kind`:

| Event | Payload | Triggers |
| --- | --- | --- |
| `reconnected` | — | full device **and** entity refresh |
| `device_updated` | `device_id?` | device refresh |
| `area_updated` | — | device refresh (area names are denormalised onto devices) |
| `entity_updated` | `entity_id?` | entity refresh |
| `entity_deleted` | `entity_id?` | entity refresh |

The id fields are optional because HA emits broad registry-change events without one. `None` means "refresh everything in that scope" — the handler never assumes an id is present.

## HA change → browser

```mermaid
sequenceDiagram
    autonumber
    participant HA as "Home Assistant"
    participant C as WebSocketHAClient
    participant M as "on_event (main.py)"
    participant Cache as "RegistryCache /<br/>EntityRegistryCache"
    participant T as DeletionTracker
    participant DB as SQLite
    participant B as EventBroker
    participant SSE as "GET /api/events"
    participant FE as "useLiveEvents"
    participant Q as "TanStack Query"

    HA-->>C: registry_updated
    C->>M: HAEvent (discriminated on kind)
    M->>M: loop.create_task(...) — handler stays sync
    M->>Cache: await refresh()
    Cache->>Cache: deep-copy snapshot, reload, diff
    Cache-->>M: Diff(added, removed, updated)
    M->>T: handle_diff_from_cache()
    T->>DB: record_deletion / mark_reappeared
    T->>T: state[id] = {reappeared: True}
    M->>DB: session.commit()
    M->>B: publish({kind: "devices_changed"})
    B->>SSE: fan out to each subscriber queue
    SSE-->>FE: text/event-stream
    FE->>Q: invalidateQueries(["devices"])
    Q->>SSE: refetch GET /api/devices
    Note over Q: rules re-evaluated server-side<br/>on the refetch, not on the event
```

Four things this diagram is meant to make obvious:

- **`on_event` is synchronous and does no work.** It only schedules tasks on the running loop. HA's WebSocket read loop is never blocked by a database write.
- **The SSE payload carries no data**, only a `kind`. It is a cache-invalidation signal; the frontend always refetches through the normal REST endpoint. One code path for rendering, whether the trigger was a poll, a user action, or an HA event.
- **Rules are evaluated on read**, not on event. There is no stored issue table — `api/devices.py` runs `RuleEngine.evaluate` per request against current cache state.
- **`EventBroker` is a plain fan-out** over per-subscriber `asyncio.Queue`s using `put_nowait`, so a slow SSE client cannot block a publish.

## Safety resync

Events can be missed — a dropped socket, an HA restart, a registry change HA doesn't announce. `_safety_resync_loop` refreshes both caches every 5 minutes, runs both tracker diffs, commits, and publishes `devices_changed` / `entities_changed` **only if the corresponding diff is non-empty**, so a quiet system produces no SSE traffic. Failures are logged and swallowed; the loop never dies.

The same work is exposed on demand at `POST /api/resync`, driven by the frontend's `ResyncButton`.

## Browser change → HA

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant P as "Page (e.g. EditDeviceDrawer)"
    participant API as "PATCH /api/devices/{id}"
    participant C as WebSocketHAClient
    participant HA as "Home Assistant"

    U->>P: rename / assign room / delete
    P->>API: mutation via openapi-fetch
    API->>C: update_device(id, HADeviceUpdate)
    Note over API,C: extra="forbid" + model_dump(exclude_unset=True)<br/>only explicitly-set fields are sent
    C->>HA: config/device_registry/update
    HA-->>C: device_registry_updated
    Note over C,HA: rejoins the read path above —<br/>the UI updates from HA's echo,<br/>not from an optimistic local write
```

There is no optimistic update of the cache. The write goes to HA, HA echoes it back as an event, and the event drives the refresh. Slightly more latency, but the cache can never drift from HA by claiming a write succeeded when it didn't.

`None` in a patch model means "clear this field", which is why `exclude_unset=True` (not `exclude_none=True`) is what gets sent.

## Startup and teardown

`create_app`'s lifespan wires everything in dependency order: client → device cache → entity cache → session → tracker → broker → policies → rule engine → `AppState` → event subscription → resync loop → policy watcher.

Teardown ordering is load-bearing and duplicated in two places — a `BaseException` handler covering partial startup, and the `finally` after `yield` covering normal shutdown. Both unsubscribe, cancel the resync and watcher tasks, stop the client, close the session, and dispose the engine. Once `client.start()` has succeeded, any later failure **must** stop the client before re-raising, or a live WebSocket leaks.

`AppState` is a mutable dataclass on `app.state.store`, read by routers through the `app_state` FastAPI dependency. Most fields are set once at startup; three are reassigned at runtime — `engine`, `policies_file`, and `policies_error`, on policy reload.
