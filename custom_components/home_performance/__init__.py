"""Home Performance integration for Home Assistant.

Analyze and monitor your home's thermal performance, energy efficiency,
and comfort metrics.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN
from .coordinator import HomePerformanceCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Performance from a config entry."""
    _LOGGER.debug("Setting up Home Performance integration")

    coordinator = HomePerformanceCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register frontend card (only once)
    if "frontend_registered" not in hass.data[DOMAIN]:
        await _async_register_frontend(hass)
        hass.data[DOMAIN]["frontend_registered"] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Register the frontend static path for the card."""
    import os
    
    www_path = os.path.join(os.path.dirname(__file__), "www")
    
    if os.path.isdir(www_path):
        try:
            await hass.http.async_register_static_paths([
                StaticPathConfig(
                    "/home_performance",
                    www_path,
                    cache_headers=False
                )
            ])
            _LOGGER.info(
                "Home Performance card registered at /home_performance/home-performance-card.js"
            )
        except Exception as err:
            _LOGGER.warning("Could not register frontend path: %s", err)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Home Performance integration")

    # Save data before unloading
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        coordinator = hass.data[DOMAIN][entry.entry_id]
        _LOGGER.info("Saving data before unload for zone %s", coordinator.zone_name)
        await coordinator.async_save_data()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    return await async_setup_entry(hass, entry)
