"""Frontend registration for Home Performance integration.

This module handles automatic registration of the Lovelace card
in Home Assistant's frontend resources.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers.event import async_call_later

from ..const import JSMODULES, URL_BASE

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Path to the www folder containing the card JS
WWW_PATH = Path(__file__).parent.parent / "www"


class JSModuleRegistration:
    """Register JavaScript modules in Home Assistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the registrar."""
        self.hass = hass
        self.lovelace = self.hass.data.get("lovelace")

    async def async_register(self) -> None:
        """Register frontend resources."""
        await self._async_register_path()
        # Register modules only if Lovelace is in storage mode
        if self.lovelace and self.lovelace.mode == "storage":
            await self._async_wait_for_lovelace_resources()
        else:
            _LOGGER.debug(
                "Lovelace not in storage mode. Manual resource registration required: %s",
                f"{URL_BASE}/{JSMODULES[0]['filename']}",
            )

    async def _async_register_path(self) -> None:
        """Register the static HTTP path."""
        try:
            await self.hass.http.async_register_static_paths(
                [StaticPathConfig(URL_BASE, str(WWW_PATH), False)]
            )
            _LOGGER.debug("Static path registered: %s -> %s", URL_BASE, WWW_PATH)
        except RuntimeError:
            _LOGGER.debug("Static path already registered: %s", URL_BASE)

    async def _async_wait_for_lovelace_resources(self) -> None:
        """Wait for Lovelace resources to be loaded."""

        async def _check_loaded(_now: Any) -> None:
            if self.lovelace.resources.loaded:
                await self._async_register_modules()
            else:
                _LOGGER.debug("Lovelace resources not loaded, retrying in 5s")
                async_call_later(self.hass, 5, _check_loaded)

        await _check_loaded(0)

    async def _async_register_modules(self) -> None:
        """Register or update JavaScript modules."""
        _LOGGER.debug("Installing JavaScript modules")

        # Get existing resources from this integration
        existing_resources = [
            r
            for r in self.lovelace.resources.async_items()
            if r["url"].startswith(URL_BASE)
        ]

        for module in JSMODULES:
            url = f"{URL_BASE}/{module['filename']}"
            registered = False

            for resource in existing_resources:
                if self._get_path(resource["url"]) == url:
                    registered = True
                    # Check if update is needed
                    if self._get_version(resource["url"]) != module["version"]:
                        _LOGGER.info(
                            "Updating %s to version %s",
                            module["name"],
                            module["version"],
                        )
                        await self.lovelace.resources.async_update_item(
                            resource["id"],
                            {
                                "res_type": "module",
                                "url": f"{url}?v={module['version']}",
                            },
                        )
                    break

            if not registered:
                _LOGGER.info(
                    "Registering %s version %s",
                    module["name"],
                    module["version"],
                )
                await self.lovelace.resources.async_create_item(
                    {
                        "res_type": "module",
                        "url": f"{url}?v={module['version']}",
                    }
                )

    async def async_unregister(self) -> None:
        """Unregister JavaScript modules (for cleanup on uninstall)."""
        if not self.lovelace or self.lovelace.mode != "storage":
            return

        if not self.lovelace.resources.loaded:
            return

        existing_resources = [
            r
            for r in self.lovelace.resources.async_items()
            if r["url"].startswith(URL_BASE)
        ]

        for resource in existing_resources:
            _LOGGER.info("Unregistering resource: %s", resource["url"])
            await self.lovelace.resources.async_delete_item(resource["id"])

    @staticmethod
    def _get_path(url: str) -> str:
        """Extract path from URL (remove query string)."""
        return url.split("?")[0]

    @staticmethod
    def _get_version(url: str) -> str | None:
        """Extract version from URL query string."""
        if "?v=" in url:
            return url.split("?v=")[1]
        return None
