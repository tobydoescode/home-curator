"""FastAPI app factory and lifespan — wires every component together."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from home_curator.api import devices as devices_api, exceptions as exceptions_api
from home_curator.api.deps import AppState
from home_curator.config import Settings
from home_curator.deletion_tracker import DeletionTracker
from home_curator.events.broker import EventBroker
from home_curator.ha_client.base import HAClient
from home_curator.ha_client.websocket import WebSocketHAClient
from home_curator.policies.loader import load_policies_file
from home_curator.registry_cache.cache import RegistryCache
from home_curator.rules.base import EvaluationContext
from home_curator.rules.engine import RuleEngine
from home_curator.storage.db import make_engine, make_session_factory
from home_curator.storage.exceptions_repo import ExceptionsRepo

log = logging.getLogger(__name__)


async def _safety_resync_loop(
    cache: RegistryCache,
    tracker: DeletionTracker,
    broker: EventBroker,
    session_commit,
) -> None:
    while True:
        await asyncio.sleep(5 * 60)
        try:
            diff = await cache.refresh()
            tracker.handle_diff_from_cache()
            session_commit()
            if diff.added or diff.removed or diff.updated:
                await broker.publish({"kind": "devices_changed"})
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
        unsub = None
        try:
            cache = RegistryCache(client)
            await cache.load()
            session = session_factory()
            tracker = DeletionTracker(cache=cache, session=session)
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

            def on_event(_e):
                # broker.publish only enqueues; scheduling it as a task just
                # so we can call publish from a sync callback.
                asyncio.get_running_loop().create_task(
                    broker.publish({"kind": "devices_changed"})
                )

            unsub = client.subscribe(on_event)
            task = asyncio.create_task(
                _safety_resync_loop(cache, tracker, broker, session.commit)
            )

            app.state.store = AppState(
                ha=client,
                cache=cache,
                tracker=tracker,
                engine=engine,
                policies_file=load.file,
                policies_error=load.error,
                session_factory=session_factory,
                broker=broker,
            )
        except BaseException:
            if unsub is not None:
                unsub()
            if task is not None:
                task.cancel()
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
            await client.stop()
            if session is not None:
                session.close()

    app = FastAPI(lifespan=lifespan, title="Home Curator")

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    app.include_router(devices_api.router)
    app.include_router(exceptions_api.router)

    return app


# Uvicorn entrypoint — created lazily so test imports don't touch the filesystem.
def _lazy_app() -> FastAPI:
    return create_app()


app = _lazy_app()
