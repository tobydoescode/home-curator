"""Home Assistant client boundary — Protocol, implementations, and models."""
from home_curator.ha_client.base import EventHandler, HAClient
from home_curator.ha_client.fake import FakeHAClient
from home_curator.ha_client.models import (
    AreaUpdatedEvent,
    DeviceUpdatedEvent,
    EntityDeletedEvent,
    EntityUpdatedEvent,
    HAArea,
    HADevice,
    HADeviceEntityRef,
    HADeviceUpdate,
    HAEntity,
    HAEntityUpdate,
    HAEvent,
    ReconnectedEvent,
)
from home_curator.ha_client.websocket import WebSocketHAClient

__all__ = [
    "AreaUpdatedEvent",
    "DeviceUpdatedEvent",
    "EntityDeletedEvent",
    "EntityUpdatedEvent",
    "EventHandler",
    "FakeHAClient",
    "HAArea",
    "HAClient",
    "HADevice",
    "HADeviceEntityRef",
    "HADeviceUpdate",
    "HAEntity",
    "HAEntityUpdate",
    "HAEvent",
    "ReconnectedEvent",
    "WebSocketHAClient",
]
