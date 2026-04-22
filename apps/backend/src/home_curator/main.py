import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    cache: RegistryCache, tracker: DeletionTracker, broker: EventBroker
) -> None:
    while True:
        await asyncio.sleep(5 * 60)
        try:
            diff = await cache.refresh()
            tracker.handle_diff_from_cache()
            if diff.added or diff.removed or diff.updated:
                await broker.publish({"kind": "devices_changed"})
        except Exception:
            log.exception("safety resync failed")


def create_app(
    ha_client: HAClient | None = None, settings: Settings | None = None
) -> FastAPI:
    settings = settings or Settings()
    engine_db = make_engine(settings.db_path)
    session_factory = make_session_factory(engine_db)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if ha_client is not None:
            client: HAClient = ha_client
        else:
            ha_url = settings.ha_url
            assert ha_url is not None, "HA_URL must be set (or SUPERVISOR_TOKEN to use auto-discovery)"
            ws_url = ha_url.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
            client = WebSocketHAClient(
                url=ws_url,
                token=settings.effective_token or "",
            )

        await client.start()
        cache = RegistryCache(client)
        await cache.load()
        session = session_factory()
        tracker = DeletionTracker(cache=cache, session=session)
        broker = EventBroker()
        load = load_policies_file(settings.policies_path)
        ctx = EvaluationContext(
            area_name_to_id=cache.area_name_to_id(),
            area_id_to_name=cache.area_id_to_name(),
            exceptions=ExceptionsRepo(session).all_acknowledged_keys(),
        )
        engine = (
            RuleEngine.compile(load.file, ctx) if load.file else RuleEngine(compiled=[])
        )

        def on_event(e):
            asyncio.create_task(broker.publish({"kind": "devices_changed"}))

        unsub = client.subscribe(on_event)
        task = asyncio.create_task(_safety_resync_loop(cache, tracker, broker))

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
        try:
            yield
        finally:
            unsub()
            task.cancel()
            await client.stop()
            session.close()

    app = FastAPI(lifespan=lifespan, title="Home Curator")

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    return app


# Uvicorn entrypoint
app = create_app()
