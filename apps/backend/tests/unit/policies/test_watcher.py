import asyncio
from pathlib import Path

import pytest

from home_curator.policies import watcher

POLICIES = Path("/config/home-curator/policies.yaml")


def _yields(*batches):
    """Fake `awatch` that emits the given batches, then stops the watcher.

    Paths are absolute, as watchfiles reports them — the earlier fixture used
    a bare filename, which no longer matches once the watcher filters on the
    file it was asked to watch.
    """

    async def _awatch(_path):
        for batch in batches:
            yield batch
        raise asyncio.CancelledError

    return _awatch


async def _run(monkeypatch, awatch, on_change) -> None:
    monkeypatch.setattr(watcher, "awatch", awatch)
    with pytest.raises(asyncio.CancelledError):
        await watcher.watch_policies(POLICIES, on_change)


@pytest.mark.asyncio
async def test_watch_policies_calls_on_change(monkeypatch):
    calls = 0

    async def on_change():
        nonlocal calls
        calls += 1

    await _run(monkeypatch, _yields({("modified", str(POLICIES))}), on_change)

    assert calls == 1


@pytest.mark.asyncio
async def test_watch_policies_swallows_on_change_errors(monkeypatch):
    calls = 0

    async def on_change():
        nonlocal calls
        calls += 1
        raise RuntimeError("reload failed")

    await _run(monkeypatch, _yields({("modified", str(POLICIES))}), on_change)

    assert calls == 1


@pytest.mark.asyncio
async def test_changes_to_other_files_are_ignored(monkeypatch):
    """The whole directory is watched, but only one file matters.

    Atomic saves write a temp file alongside `policies.yaml` and rename it,
    so without this filter every save would trigger an extra recompile — and
    an editor swapfile would trigger one for no reason at all.
    """
    calls = 0

    async def on_change():
        nonlocal calls
        calls += 1

    await _run(
        monkeypatch,
        _yields(
            {("added", "/config/home-curator/.policies.yaml.tmp")},
            {("deleted", "/config/home-curator/notes.txt.swp")},
        ),
        on_change,
    )

    assert calls == 0


@pytest.mark.asyncio
async def test_a_batch_touching_the_file_reloads_once(monkeypatch):
    """A save emits several events; one reload is enough."""
    calls = 0

    async def on_change():
        nonlocal calls
        calls += 1

    await _run(
        monkeypatch,
        _yields(
            {
                ("added", "/config/home-curator/.policies.yaml.tmp"),
                ("modified", str(POLICIES)),
            }
        ),
        on_change,
    )

    assert calls == 1
