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

from ..const import DOMAIN, JSMODULES, URL_BASE

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

WWW_PATH = Path(__file__).parent.parent / "www"

LEGACY_URL_BASE = f"/{DOMAIN}"

_MAX_WAIT_RETRIES = 12


class JSModuleRegistration:
    """Register JavaScript modules in Home Assistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the registrar."""
        self.hass = hass
        self.lovelace = self.hass.data.get("lovelace")

    async def async_register(self) -> None:
        """Register frontend resources."""
        await self._async_register_path()
        if self.lovelace and self.lovelace.mode == "storage":
            await self._async_wait_for_lovelace_resources()
        else:
            _LOGGER.debug(
                "Lovelace not in storage mode. Manual resource registration required: %s",
                f"{URL_BASE}/{JSMODULES[0]['filename']}",
            )

    async def _async_register_path(self) -> None:
        """Register static HTTP paths (current + legacy for backward compat)."""
        paths_to_register = [
            StaticPathConfig(URL_BASE, str(WWW_PATH), False),
            StaticPathConfig(LEGACY_URL_BASE, str(WWW_PATH), False),
        ]
        for path_config in paths_to_register:
            try:
                await self.hass.http.async_register_static_paths([path_config])
                _LOGGER.debug("Static path registered: %s -> %s", path_config.url_path, WWW_PATH)
            except RuntimeError:
                _LOGGER.debug("Static path already registered: %s", path_config.url_path)

    async def _async_wait_for_lovelace_resources(self) -> None:
        """Wait for Lovelace resources to be loaded (max ~60s)."""
        retries = 0

        async def _check_loaded(_now: Any) -> None:
            nonlocal retries
            if self.lovelace.resources.loaded:
                await self._async_register_modules()
            elif retries < _MAX_WAIT_RETRIES:
                retries += 1
                _LOGGER.debug("Lovelace resources not loaded, retrying in 5s (%s/%s)", retries, _MAX_WAIT_RETRIES)
                async_call_later(self.hass, 5, _check_loaded)
            else:
                _LOGGER.warning(
                    "Lovelace resources did not load after %ss. "
                    "Card resource may need manual registration: %s",
                    _MAX_WAIT_RETRIES * 5,
                    f"{URL_BASE}/{JSMODULES[0]['filename']}",
                )

        await _check_loaded(0)

    async def _async_register_modules(self) -> None:
        """Register or update JavaScript modules, then clean up legacy URLs."""
        _LOGGER.debug("Installing JavaScript modules")

        existing_resources = [r for r in self.lovelace.resources.async_items() if r["url"].startswith(URL_BASE)]

        for module in JSMODULES:
            url = f"{URL_BASE}/{module['filename']}"
            try:
                registered = False
                for resource in existing_resources:
                    if self._get_path(resource["url"]) == url:
                        registered = True
                        if self._get_version(resource["url"]) != module["version"]:
                            _LOGGER.info("Updating %s to version %s", module["name"], module["version"])
                            await self.lovelace.resources.async_update_item(
                                resource["id"],
                                {"res_type": "module", "url": f"{url}?v={module['version']}"},
                            )
                        break

                if not registered:
                    _LOGGER.info("Registering %s version %s", module["name"], module["version"])
                    await self.lovelace.resources.async_create_item(
                        {"res_type": "module", "url": f"{url}?v={module['version']}"}
                    )
            except Exception:
                _LOGGER.exception("Failed to register/update resource %s", module["name"])

        await self._async_cleanup_legacy_resources()

    async def _async_cleanup_legacy_resources(self) -> None:
        """Remove old resources that used the underscore URL (/home_performance/...).

        Only removes legacy resources; the new /home-performance/ resource
        must already be registered before this runs.
        """
        legacy_prefixes = [
            f"{LEGACY_URL_BASE}/",
        ]

        for resource in self.lovelace.resources.async_items():
            url = resource.get("url", "")
            if any(url.startswith(prefix) for prefix in legacy_prefixes):
                try:
                    _LOGGER.info("Removing legacy resource: %s", url)
                    await self.lovelace.resources.async_delete_item(resource["id"])
                except Exception:
                    _LOGGER.exception("Failed to remove legacy resource: %s", url)

    async def async_unregister(self) -> None:
        """Unregister JavaScript modules (for cleanup on uninstall)."""
        if not self.lovelace or self.lovelace.mode != "storage":
            return

        if not self.lovelace.resources.loaded:
            return

        existing_resources = [r for r in self.lovelace.resources.async_items() if r["url"].startswith(URL_BASE)]

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
