"""Creating an area must activate room overrides that referenced it.

Naming-convention room overrides are written against an area *name* and
resolved to an area id when the rule is compiled, so a rule naming a room
that does not exist yet compiles with an error.

This used to be papered over by resolving lazily inside `evaluate()` — which
made evaluation mutate the shared compiled rule while running concurrently in
FastAPI's threadpool. Resolution now happens once at compile time, so an
`area_registry_updated` event has to trigger a recompile instead. Without
that, the override would stay dormant until the next policy save or restart.
"""

import pytest
from fastapi.testclient import TestClient

from home_curator.ha_client.models import AreaUpdatedEvent, HAArea

_POLICY = """
version: 1
policies:
  - id: naming-convention
    type: naming_convention
    enabled: true
    severity: warning
    global:
      preset: snake_case
    rooms:
      - room: Basement
        preset: kebab-case
""".strip()


@pytest.fixture
def client_with_room_override(tmp_path, fake_ha, monkeypatch):
    from sqlalchemy import create_engine

    from home_curator.config import Settings
    from home_curator.main import create_app
    from home_curator.storage.models import Base

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "policies.yaml").write_text(_POLICY)

    engine = create_engine(f"sqlite:///{tmp_path / 'curator.db'}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HA_TOKEN", "devtoken")
    with TestClient(create_app(ha_client=fake_ha, settings=Settings())) as client:
        yield client


def _compile_error(client: TestClient) -> str | None:
    body = client.get("/api/policies").json()
    entry = next(p for p in body["policies"] if p["id"] == "naming-convention")
    return entry["compile_error"]


def test_unknown_room_is_reported_as_a_compile_error(client_with_room_override):
    assert "Basement" in (_compile_error(client_with_room_override) or "")


@pytest.mark.asyncio
async def test_creating_the_area_activates_the_override(
    client_with_room_override, fake_ha
):
    client = client_with_room_override
    assert _compile_error(client) is not None

    fake_ha.set_areas([
        *(await fake_ha.get_areas()),
        HAArea(id="basement_id", name="Basement"),
    ])
    await fake_ha.emit(AreaUpdatedEvent())

    # The event is handled on the loop; poll rather than assume immediacy.
    for _ in range(50):
        if _compile_error(client) is None:
            break
        await _sleep()
    assert _compile_error(client) is None, (
        "creating the area did not recompile the engine, so the room "
        "override stayed dormant"
    )


async def _sleep() -> None:
    import asyncio

    await asyncio.sleep(0.05)
