"""FastAPI app factory and lifespan — wires every component together."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from home_curator.api import (
    areas as areas_api,
)
from home_curator.api import (
    cache as cache_api,
)
from home_curator.api import (
    config_api,
)
from home_curator.api import (
    devices as devices_api,
)
from home_curator.api import (
    entities as entities_api,
)
from home_curator.api import (
    events as events_api,
)
from home_curator.api import (
    exceptions as exceptions_api,
)
from home_curator.api import (
    policies as policies_api,
)
from home_curator.api.deps import AppState
from home_curator.api.schemas import HealthResponse
from home_curator.config import Settings
from home_curator.deletion_tracker import DeletionTracker
from home_curator.events.broker import EventBroker
from home_curator.ha_client.base import HAClient
from home_curator.ha_client.models import HAEvent
from home_curator.ha_client.websocket import WebSocketHAClient
from home_curator.policies.loader import load_policies_file
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
    session_commit,
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


def create_app(
    ha_client: HAClient | None = None, settings: Settings | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Build effective config inside lifespan so importing this module has
        # no filesystem side-effect (make_engine creates data_dir).
        effective_settings = settings or Settings()
        engine_db = make_engine(effective_settings.db_path)
        session_factory = make_session_factory(engine_db)

        if ha_client is not None:
            client: HAClient = ha_client
        else:
            ha_url = effective_settings.ha_url
            assert ha_url is not None, (
                "HA_URL must be set (or SUPERVISOR_TOKEN to use auto-discovery)"
            )
            ws_url = (
                ha_url.replace("https://", "wss://").replace("http://", "ws://")
                + "/api/websocket"
            )
            client = WebSocketHAClient(
                url=ws_url,
                token=effective_settings.effective_token or "",
            )

        await client.start()
        # From here on, failures must stop the client before re-raising.
        session = None
        task = None
        watcher_task = None
        unsub = None
        try:
            cache = RegistryCache(client)
            await cache.load()
            entity_cache = EntityRegistryCache(
                client,
                area_lookup=cache.area_id_to_name,
                device_lookup=cache.device,
            )
            await entity_cache.load()
            session = session_factory()
            tracker = DeletionTracker(cache=cache, session=session, entity_cache=entity_cache)
            broker = EventBroker()
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

            async def _refresh_and_publish_devices():
                try:
                    await cache.refresh()
                    tracker.handle_diff_from_cache()
                    session.commit()
                except Exception:
                    log.exception("registry refresh on HA event failed")
                await broker.publish({"kind": "devices_changed"})

            async def _refresh_and_publish_entity(entity_id: str | None, kind: str):
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
                        loop.create_task(_refresh_and_publish_devices())
                    case "reconnected":
                        loop.create_task(_refresh_and_publish_devices())
                        loop.create_task(
                            _refresh_and_publish_entity(None, "entities_changed")
                        )

            unsub = client.subscribe(on_event)
            task = asyncio.create_task(
                _safety_resync_loop(cache, entity_cache, tracker, broker, session.commit)
            )

            app.state.store = AppState(
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

            async def reload_policies():
                load_ = load_policies_file(effective_settings.policies_path)
                app.state.store.policies_error = load_.error
                # Keep last-good rules loaded on invalid reloads.
                if load_.file is None:
                    await broker.publish({"kind": "policies_changed"})
                    return
                with session_scope(session_factory) as s:
                    ctx_ = EvaluationContext(
                        area_name_to_id=cache.area_name_to_id(),
                        area_id_to_name=cache.area_id_to_name(),
                        exceptions=ExceptionsRepo(s).all_acknowledged_keys(),
                    )
                app.state.store.engine = RuleEngine.compile(load_.file, ctx_)
                app.state.store.policies_file = load_.file
                await broker.publish({"kind": "policies_changed"})

            from home_curator.policies.watcher import watch_policies
            watcher_task = asyncio.create_task(
                watch_policies(effective_settings.policies_path, reload_policies)
            )
        except BaseException:
            if unsub is not None:
                unsub()
            if task is not None:
                task.cancel()
            if watcher_task is not None:
                watcher_task.cancel()
            if session is not None:
                session.close()
            await client.stop()
            raise

        try:
            yield
        finally:
            if unsub is not None:
                unsub()
            if task is not None:
                task.cancel()
            if watcher_task is not None:
                watcher_task.cancel()
            await client.stop()
            if session is not None:
                session.close()

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
    # /app/static). Mount last so /api routes take precedence.
    static_dir = os.environ.get("STATIC_DIR", "/app/static")
    if os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


# Uvicorn entrypoint — created lazily so test imports don't touch the filesystem.
def _lazy_app() -> FastAPI:
    return create_app()


app = _lazy_app()
