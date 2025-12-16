"""Home Performance integration for Home Assistant.

Analyze and monitor your home's thermal performance, energy efficiency,
and comfort metrics. Supports multiple zones/rooms.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

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

# Key for storing zones in config entry data
CONF_ZONES = "zones"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Performance from a config entry."""
    _LOGGER.debug("Setting up Home Performance integration")

    hass.data.setdefault(DOMAIN, {})
    
    # Register frontend card (only once globally)
    if "frontend_registered" not in hass.data[DOMAIN]:
        await _async_register_frontend(hass)
        hass.data[DOMAIN]["frontend_registered"] = True

    # Initialize storage for this entry
    hass.data[DOMAIN][entry.entry_id] = {"zones": {}}

    # Create a coordinator for each zone
    zones_config = entry.data.get(CONF_ZONES, {})
    
    if not zones_config:
        _LOGGER.warning("No zones configured in entry data")
        # Migration: if old format (single zone in entry.data), convert it
        if "zone_name" in entry.data:
            _LOGGER.info("Migrating from single-zone to multi-zone format")
            zones_config = await _migrate_single_to_multi(hass, entry)
    
    for zone_id, zone_data in zones_config.items():
        zone_name = zone_data.get("zone_name", zone_id)
        _LOGGER.info("Setting up zone: %s (id: %s)", zone_name, zone_id)
        
        try:
            coordinator = HomePerformanceCoordinator(hass, entry, zone_id, zone_data)
            await coordinator.async_config_entry_first_refresh()
            hass.data[DOMAIN][entry.entry_id]["zones"][zone_id] = coordinator
        except Exception as err:
            _LOGGER.error("Failed to setup zone %s: %s", zone_name, err)
            continue

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload when config entry is updated (options or data change)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    return True


async def _migrate_single_to_multi(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Migrate old single-zone format to new multi-zone format."""
    import uuid
    
    zone_id = str(uuid.uuid4())[:8]
    zone_data = {k: v for k, v in entry.data.items() if k != CONF_ZONES}
    
    new_data = {CONF_ZONES: {zone_id: zone_data}}
    
    hass.config_entries.async_update_entry(entry, data=new_data)
    
    return new_data[CONF_ZONES]


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry update - reload the integration."""
    _LOGGER.info("Config entry updated, reloading integration")
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Register the frontend static path and Lovelace resource for the card."""
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
            
            # Auto-register Lovelace resource (storage mode only)
            await _async_register_lovelace_resource(hass)
            
        except Exception as err:
            _LOGGER.warning("Could not register frontend path: %s", err)


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Register the card as a Lovelace resource (storage mode only)."""
    url = "/home_performance/home-performance-card.js"
    
    try:
        lovelace_data = hass.data.get("lovelace")
        if lovelace_data is None:
            _LOGGER.debug("Lovelace not loaded yet, skipping auto-registration")
            return
        
        resources = lovelace_data.get("resources")
        if resources is None:
            _LOGGER.debug(
                "Lovelace resources not available (YAML mode?). "
                "Add resource manually: %s", url
            )
            return
        
        existing = await resources.async_get_resources()
        for resource in existing:
            if resource.get("url") == url:
                _LOGGER.debug("Lovelace resource already registered: %s", url)
                return
        
        await resources.async_create_resource(url, "module")
        _LOGGER.info("Lovelace resource auto-registered: %s", url)
        
    except Exception as err:
        _LOGGER.debug(
            "Could not auto-register Lovelace resource (manual step may be needed): %s",
            err
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Home Performance integration")

    # Save data for all zones before unloading
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    zones = entry_data.get("zones", {})
    
    for zone_id, coordinator in zones.items():
        _LOGGER.info("Saving data before unload for zone %s", coordinator.zone_name)
        try:
            await coordinator.async_save_data()
        except Exception as err:
            _LOGGER.warning("Failed to save data for zone %s: %s", zone_id, err)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    return await async_setup_entry(hass, entry)
