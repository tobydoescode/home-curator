from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from home_curator.config import Settings
from home_curator.deletion_tracker import DeletionTracker
from home_curator.events.broker import EventBroker
from home_curator.ha_client.base import HAClient
from home_curator.policies.schema import PoliciesFile
from home_curator.registry_cache.cache import RegistryCache
from home_curator.registry_cache.entity_cache import EntityRegistryCache
from home_curator.rules.engine import RuleEngine


@dataclass
class AppState:
    # The settings this app was created with. Handlers must read these
    # rather than constructing their own: `Settings()` reloads `.env` from
    # disk and ignores whatever `create_app` was given, so a handler that
    # builds its own silently disagrees with the rest of the app.
    settings: Settings
    ha: HAClient
    cache: RegistryCache
    entity_cache: EntityRegistryCache
    tracker: DeletionTracker
    engine: RuleEngine
    policies_file: PoliciesFile | None
    policies_error: str | None
    session_factory: sessionmaker[Session]
    broker: EventBroker


def app_state(request: Request) -> AppState:
    state = request.app.state.store
    assert isinstance(state, AppState)
    return state
