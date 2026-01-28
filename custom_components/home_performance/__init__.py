"""Home Performance integration for Home Assistant.

Analyze and monitor your home's thermal performance, energy efficiency,
and comfort metrics. Supports multiple zones (one config entry per zone).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, VERSION
from .coordinator import HomePerformanceCoordinator
from .frontend import JSModuleRegistration

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# Service names
SERVICE_RESET_HISTORY = "reset_history"
SERVICE_RESET_ALL = "reset_all"

# Service schemas
RESET_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("zone_name"): cv.string,
    }
)

RESET_ALL_SCHEMA = vol.Schema(
    {
        vol.Required("zone_name"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Home Performance component."""
    hass.data.setdefault(DOMAIN, {})

    # Register WebSocket command for version check
    websocket_api.async_register_command(hass, websocket_get_version)

    # Setup frontend registration
    async def _async_setup_frontend(_hass: HomeAssistant) -> None:
        """Register frontend resources after Home Assistant is started."""
        module_register = JSModuleRegistration(hass)
        await module_register.async_register()

    # async_at_started handles both cases:
    # - If HA is already running: executes immediately
    # - If HA is starting: waits for EVENT_HOMEASSISTANT_STARTED
    async_at_started(hass, _async_setup_frontend)

    return True


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/version",
    }
)
@callback
def websocket_get_version(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle get version WebSocket command."""
    connection.send_result(
        msg["id"],
        {"version": VERSION},
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Performance from a config entry."""
    _LOGGER.debug("Setting up Home Performance integration for %s", entry.title)

    # Create coordinator for this zone
    coordinator = HomePerformanceCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register services (only once globally)
    if "services_registered" not in hass.data[DOMAIN]:
        await _async_register_services(hass)
        hass.data[DOMAIN]["services_registered"] = True

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload when options change
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update - reload the integration."""
    _LOGGER.info("Options updated for %s, reloading", entry.title)
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register Home Performance services."""

    async def handle_reset_history(call: ServiceCall) -> None:
        """Handle the reset_history service call.

        Clears the 7-day rolling history for a specific zone.
        Use after insulation work or to clear anomalous data.
        """
        zone_name = call.data["zone_name"]
        _LOGGER.info("Reset history service called for zone: %s", zone_name)

        # Find the coordinator for this zone
        skip_keys = ("services_registered", "last_outdoor_temp_sensor")
        found = False
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if entry_id in skip_keys:
                continue
            if isinstance(coordinator, HomePerformanceCoordinator):
                if coordinator.zone_name.lower() == zone_name.lower():
                    coordinator.reset_history()
                    found = True
                    _LOGGER.info("History reset completed for zone: %s", zone_name)
                    break

        if not found:
            _LOGGER.warning("Zone not found for reset: %s", zone_name)
            raise ValueError(f"Zone '{zone_name}' not found")

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_HISTORY,
        handle_reset_history,
        schema=RESET_HISTORY_SCHEMA,
    )

    async def handle_reset_all(call: ServiceCall) -> None:
        """Handle the reset_all service call.

        Completely resets ALL calibration data for a zone.
        Use when measurements were taken during unusual conditions.
        """
        zone_name = call.data["zone_name"]
        _LOGGER.info("Reset all data service called for zone: %s", zone_name)

        # Find the coordinator for this zone
        skip_keys = ("services_registered", "last_outdoor_temp_sensor")
        found = False
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if entry_id in skip_keys:
                continue
            if isinstance(coordinator, HomePerformanceCoordinator):
                if coordinator.zone_name.lower() == zone_name.lower():
                    coordinator.reset_all_data()
                    found = True
                    _LOGGER.info("Complete data reset completed for zone: %s", zone_name)
                    break

        if not found:
            _LOGGER.warning("Zone not found for reset: %s", zone_name)
            raise ValueError(f"Zone '{zone_name}' not found")

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_ALL,
        handle_reset_all,
        schema=RESET_ALL_SCHEMA,
    )

    _LOGGER.info("Home Performance services registered")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Home Performance for %s", entry.title)

    # Save data before unloading
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        coordinator = hass.data[DOMAIN][entry.entry_id]
        _LOGGER.info("Saving data before unload for zone %s", coordinator.zone_name)
        try:
            await coordinator.async_save_data()
        except Exception as err:
            _LOGGER.warning("Failed to save data: %s", err)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    return await async_setup_entry(hass, entry)
