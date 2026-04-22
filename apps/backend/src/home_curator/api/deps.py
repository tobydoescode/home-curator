from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.orm import sessionmaker

from home_curator.deletion_tracker import DeletionTracker
from home_curator.events.broker import EventBroker
from home_curator.ha_client.base import HAClient
from home_curator.policies.schema import PoliciesFile
from home_curator.registry_cache.cache import RegistryCache
from home_curator.rules.engine import RuleEngine


@dataclass
class AppState:
    ha: HAClient
    cache: RegistryCache
    tracker: DeletionTracker
    engine: RuleEngine
    policies_file: PoliciesFile | None
    policies_error: str | None
    session_factory: sessionmaker
    broker: EventBroker


def app_state(request: Request) -> AppState:
    return request.app.state.store
