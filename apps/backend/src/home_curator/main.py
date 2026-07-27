"""FastAPI app factory and lifespan — wires every component together."""
import asyncio
import logging
import os
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

# Aliased: the lifespan has local `cache` and `events` names, and an
# unaliased module import would be shadowed by them.
from home_curator.api import areas as areas_api
from home_curator.api import cache as cache_api
from home_curator.api import config_api
from home_curator.api import devices as devices_api
from home_curator.api import entities as entities_api
from home_curator.api import events as events_api
from home_curator.api import exceptions as exceptions_api
from home_curator.api import policies as policies_api
from home_curator.api.deps import AppState
from home_curator.api.schemas import HealthResponse
from home_curator.api.spa import mount_spa
from home_curator.config import Settings
from home_curator.deletion_tracker import DeletionTracker
from home_curator.events.broker import EventBroker
from home_curator.ha_client.base import HAClient
from home_curator.ha_client.models import HAEvent
from home_curator.ha_client.websocket import WebSocketHAClient
from home_curator.policies.loader import load_policies_file, seed_policies_file
from home_curator.policies.watcher import watch_policies
from home_curator.registry_cache.cache import RegistryCache
from home_curator.registry_cache.entity_cache import EntityRegistryCache
from home_curator.rules.base import EvaluationContext
from home_curator.rules.engine import RuleEngine
from home_curator.storage.db import make_engine, make_session_factory, session_scope
from home_curator.storage.exceptions_repo import ExceptionsRepo

log = logging.getLogger(__name__)


async def _safety_resync_loop(
    cache: RegistryCache,
    entity_cache: EntityRegistryCache,
    tracker: DeletionTracker,
    broker: EventBroker,
    session_commit: Callable[[], None],
) -> None:
    while True:
        await asyncio.sleep(5 * 60)
        try:
            dev_diff = await cache.refresh()
            ent_diff = await entity_cache.refresh()
            tracker.handle_diff_from_cache()
            tracker.handle_entity_diff_from_cache()
            session_commit()
            if dev_diff.added or dev_diff.removed or dev_diff.updated:
                await broker.publish({"kind": "devices_changed"})
            if ent_diff.added or ent_diff.removed or ent_diff.updated:
                await broker.publish({"kind": "entities_changed"})
        except Exception:
            log.exception("safety resync failed")


def _connect_to_home_assistant(settings: Settings) -> HAClient:
    """Build the websocket client from configuration.

    The URL is derived from `HA_URL` rather than configured separately, so a
    user only has to get one of them right.
    """
    ha_url = settings.ha_url
    if ha_url is None:
        raise RuntimeError(
            "HA_URL must be set (or SUPERVISOR_TOKEN, for add-on auto-discovery)"
        )
    ws_url = (
        ha_url.replace("https://", "wss://").replace("http://", "ws://")
        + "/api/websocket"
    )
    return WebSocketHAClient(url=ws_url, token=settings.effective_token or "")


def create_app(
    ha_client: HAClient | None = None, settings: Settings | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Build effective config inside lifespan so importing this module has
        # no filesystem side-effect (make_engine creates data_dir).
        effective_settings = settings or Settings()

        # Each resource registers its own cleanup as it is acquired, and the
        # stack unwinds in reverse on the way out — including when startup
        # itself fails part-way. This replaced a hand-written teardown
        # duplicated across an `except BaseException` and a `finally`, which
        # had already drifted apart: the failure path stopped the Home
        # Assistant client *after* closing the session its event callbacks
        # use, while the success path stopped it before.
        async with AsyncExitStack() as stack:
            engine_db = make_engine(effective_settings.db_path)
            stack.callback(engine_db.dispose)
            session_factory = make_session_factory(engine_db)

            # Opened before the client starts, so it is closed after the
            # client stops: in-flight event callbacks write through it.
            session = session_factory()
            stack.callback(session.close)

            client = ha_client or _connect_to_home_assistant(effective_settings)
            await client.start()
            stack.push_async_callback(client.stop)

            cache = RegistryCache(client)
            await cache.load()
            entity_cache = EntityRegistryCache(
                client,
                area_lookup=cache.area_id_to_name,
                device_lookup=cache.device,
            )
            await entity_cache.load()
            tracker = DeletionTracker(cache=cache, session=session, entity_cache=entity_cache)
            broker = EventBroker()
            # Creates the addon's config directory on a fresh install and drops
            # the baseline file in it, so the directory exists before the first
            # policy save and users can hand-edit the file as documented.
            # Not fatal if it fails — a read-only config mount should still
            # give a working, read-only app rather than refusing to boot.
            try:
                if seed_policies_file(effective_settings.policies_path):
                    log.info(
                        "Seeded default policies at %s",
                        effective_settings.policies_path,
                    )
            except OSError:
                log.exception(
                    "could not seed %s; policy edits will fail until the "
                    "directory is writable",
                    effective_settings.policies_path,
                )
            load = load_policies_file(effective_settings.policies_path)
            ctx = EvaluationContext(
                area_name_to_id=cache.area_name_to_id(),
                area_id_to_name=cache.area_id_to_name(),
                exceptions=ExceptionsRepo(session).all_acknowledged_keys(),
            )
            engine = (
                RuleEngine.compile(load.file, ctx)
                if load.file
                else RuleEngine(compiled=[])
            )

            async def _refresh_and_publish_devices() -> None:
                try:
                    await cache.refresh()
                    tracker.handle_diff_from_cache()
                    session.commit()
                except Exception:
                    log.exception("registry refresh on HA event failed")
                await broker.publish({"kind": "devices_changed"})

            async def _refresh_and_publish_entity(
                entity_id: str | None, kind: str
            ) -> None:
                try:
                    await entity_cache.refresh()
                    tracker.handle_entity_diff_from_cache()
                    session.commit()
                except Exception:
                    log.exception("entity registry refresh on HA event failed")
                # Per-entity notification first, then a broad changed event for
                # any cross-cutting listener.
                if entity_id is not None:
                    await broker.publish({"kind": kind, "entity_id": entity_id})
                await broker.publish({"kind": "entities_changed"})

            def _evaluation_context() -> EvaluationContext:
                with session_scope(session_factory) as s:
                    return EvaluationContext(
                        area_name_to_id=cache.area_name_to_id(),
                        area_id_to_name=cache.area_id_to_name(),
                        exceptions=ExceptionsRepo(s).all_acknowledged_keys(),
                    )

            async def _recompile_engine() -> None:
                """Rebuild the engine against the current area registry.

                Naming-convention room overrides are matched by area *name*
                and resolved to an area id when the rule is compiled, so a
                rule referring to a room that does not exist yet compiles
                with an error. Creating that area in Home Assistant has to
                recompile, or the override would not take effect until the
                next policy save or restart.
                """
                file_ = app.state.store.policies_file
                if file_ is None:
                    return
                app.state.store.engine = RuleEngine.compile(
                    file_, _evaluation_context()
                )

            async def _handle_area_change() -> None:
                await _refresh_and_publish_devices()
                await _recompile_engine()

            def on_event(e: HAEvent) -> None:
                loop = asyncio.get_running_loop()
                match e.kind:
                    case "device_updated":
                        loop.create_task(_refresh_and_publish_devices())
                    case "entity_updated":
                        loop.create_task(
                            _refresh_and_publish_entity(e.entity_id, "entity_updated")
                        )
                    case "entity_deleted":
                        loop.create_task(
                            _refresh_and_publish_entity(e.entity_id, "entity_deleted")
                        )
                    case "area_updated":
                        loop.create_task(_handle_area_change())
                    case "reconnected":
                        loop.create_task(_refresh_and_publish_devices())
                        loop.create_task(
                            _refresh_and_publish_entity(None, "entities_changed")
                        )

            stack.callback(client.subscribe(on_event))
            resync_task = asyncio.create_task(
                _safety_resync_loop(cache, entity_cache, tracker, broker, session.commit)
            )
            stack.callback(resync_task.cancel)

            app.state.store = AppState(
                settings=effective_settings,
                ha=client,
                cache=cache,
                entity_cache=entity_cache,
                tracker=tracker,
                engine=engine,
                policies_file=load.file,
                policies_error=load.error,
                session_factory=session_factory,
                broker=broker,
            )

            async def reload_policies() -> None:
                load_ = load_policies_file(effective_settings.policies_path)
                app.state.store.policies_error = load_.error
                # Keep last-good rules loaded on invalid reloads.
                if load_.file is None:
                    await broker.publish({"kind": "policies_changed"})
                    return
                app.state.store.engine = RuleEngine.compile(
                    load_.file, _evaluation_context()
                )
                app.state.store.policies_file = load_.file
                await broker.publish({"kind": "policies_changed"})

            watcher_task = asyncio.create_task(
                watch_policies(effective_settings.policies_path, reload_policies)
            )
            stack.callback(watcher_task.cancel)

            yield

    app = FastAPI(lifespan=lifespan, title="Home Curator")

    @app.get("/api/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        """Liveness probe. Returns 200 OK when the app is running."""
        return HealthResponse(ok=True)

    app.include_router(devices_api.router)
    app.include_router(entities_api.router)
    app.include_router(exceptions_api.router)
    app.include_router(cache_api.router)
    app.include_router(policies_api.router)
    app.include_router(events_api.router)
    app.include_router(areas_api.router)
    app.include_router(config_api.router)

    # Serve the built frontend if present (production image bundles it at
    # /app/static). Mounted last so /api routes take precedence.
    static_dir = os.environ.get("STATIC_DIR", "/app/static")
    if os.path.isdir(static_dir):
        mount_spa(app, Path(static_dir))

    return app


# Uvicorn entrypoint. Importing this module has no filesystem side-effect:
# `create_app` only registers routes, and everything that touches disk or the
# network happens inside the lifespan. (The wrapper this replaced was named
# `_lazy_app` but was called immediately, so it deferred nothing.)
app = create_app()
