"""Config flow for the test fixture integration.

Two entries are created, keyed by `slot`, so one device can be linked to two
config entries. That is the shape `WebSocketHAClient.delete_device` walks.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from . import DOMAIN


class CuratorTestConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        slot = (import_data or {}).get("slot", "primary")
        await self.async_set_unique_id(f"{DOMAIN}-{slot}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"Curator Test ({slot})", data={"slot": slot}
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self.async_step_import(user_input)
