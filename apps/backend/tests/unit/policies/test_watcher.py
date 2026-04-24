import asyncio
from pathlib import Path

import pytest

from home_curator.policies import watcher


async def one_event_then_cancel(_path):
    yield {("modified", "policies.yaml")}
    raise asyncio.CancelledError


@pytest.mark.asyncio
async def test_watch_policies_calls_on_change(monkeypatch):
    calls = 0

    async def on_change():
        nonlocal calls
        calls += 1

    monkeypatch.setattr(watcher, "awatch", one_event_then_cancel)

    with pytest.raises(asyncio.CancelledError):
        await watcher.watch_policies(Path("/config/home-curator/policies.yaml"), on_change)

    assert calls == 1


@pytest.mark.asyncio
async def test_watch_policies_swallows_on_change_errors(monkeypatch):
    calls = 0

    async def on_change():
        nonlocal calls
        calls += 1
        raise RuntimeError("reload failed")

    monkeypatch.setattr(watcher, "awatch", one_event_then_cancel)

    with pytest.raises(asyncio.CancelledError):
        await watcher.watch_policies(Path("/config/home-curator/policies.yaml"), on_change)

    assert calls == 1
