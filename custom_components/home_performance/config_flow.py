"""Config flow for Home Performance integration."""
from __future__ import annotations

import logging
from typing import Any
import uuid

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_HEATING_ENTITY,
    CONF_HEATER_POWER,
    CONF_POWER_SENSOR,
    CONF_ENERGY_SENSOR,
    CONF_ZONE_NAME,
    CONF_SURFACE,
    CONF_VOLUME,
)

_LOGGER = logging.getLogger(__name__)

# Key for storing zones in config entry data
CONF_ZONES = "zones"


def get_schema_step_zone(hass: HomeAssistant) -> vol.Schema:
    """Return schema for zone configuration step."""
    return vol.Schema(
        {
            vol.Required(CONF_ZONE_NAME): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(CONF_INDOOR_TEMP_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Required(CONF_OUTDOOR_TEMP_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Required(CONF_HEATING_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["climate", "switch", "input_boolean"])
            ),
            vol.Required(CONF_HEATER_POWER): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=100,
                    max=10000,
                    step=50,
                    unit_of_measurement="W",
                    mode="box",
                )
            ),
        }
    )


def get_schema_step_dimensions(hass: HomeAssistant) -> vol.Schema:
    """Return schema for room dimensions and optional power sensor configuration."""
    return vol.Schema(
        {
            vol.Optional(CONF_SURFACE): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=500,
                    step=0.5,
                    unit_of_measurement="m²",
                    mode="box",
                )
            ),
            vol.Optional(CONF_VOLUME): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=1500,
                    step=0.5,
                    unit_of_measurement="m³",
                    mode="box",
                )
            ),
            vol.Optional(CONF_POWER_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="power",
                )
            ),
            vol.Optional(CONF_ENERGY_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="energy",
                )
            ),
        }
    )


def validate_zone_input(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, str]:
    """Validate zone configuration input."""
    errors: dict[str, str] = {}
    
    indoor_temp = user_input.get(CONF_INDOOR_TEMP_SENSOR)
    outdoor_temp = user_input.get(CONF_OUTDOOR_TEMP_SENSOR)
    heating = user_input.get(CONF_HEATING_ENTITY)

    if not hass.states.get(indoor_temp):
        errors[CONF_INDOOR_TEMP_SENSOR] = "entity_not_found"
    if not hass.states.get(outdoor_temp):
        errors[CONF_OUTDOOR_TEMP_SENSOR] = "entity_not_found"
    if not hass.states.get(heating):
        errors[CONF_HEATING_ENTITY] = "entity_not_found"

    heater_power = user_input.get(CONF_HEATER_POWER)
    if not heater_power or heater_power <= 0:
        errors[CONF_HEATER_POWER] = "invalid_power"
    
    return errors


class HomePerformanceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Performance."""

    VERSION = 2  # Incremented for new multi-zone structure

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._zone_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - first zone configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = validate_zone_input(self.hass, user_input)

            if not errors:
                self._zone_data.update(user_input)
                return await self.async_step_dimensions()

        return self.async_show_form(
            step_id="user",
            data_schema=get_schema_step_zone(self.hass),
            errors=errors,
            description_placeholders={"name": "Home Performance"},
        )

    async def async_step_dimensions(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the room dimensions configuration step."""
        if user_input is not None:
            self._zone_data.update(user_input)

            # Generate unique zone ID
            zone_id = str(uuid.uuid4())[:8]
            zone_name = self._zone_data[CONF_ZONE_NAME]
            
            # Create the hub with first zone
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Home Performance",
                data={
                    CONF_ZONES: {
                        zone_id: self._zone_data
                    }
                },
            )

        return self.async_show_form(
            step_id="dimensions",
            data_schema=get_schema_step_dimensions(self.hass),
        )

    # -------------------------------------------------------------------------
    # Add Device Flow (for adding new zones after initial setup)
    # -------------------------------------------------------------------------
    
    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a new zone/device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = validate_zone_input(self.hass, user_input)
            
            # Check if zone name already exists
            entry = self._get_entry()
            if entry:
                existing_zones = entry.data.get(CONF_ZONES, {})
                for zone_data in existing_zones.values():
                    if zone_data.get(CONF_ZONE_NAME, "").lower() == user_input.get(CONF_ZONE_NAME, "").lower():
                        errors[CONF_ZONE_NAME] = "already_configured"
                        break

            if not errors:
                self._zone_data.update(user_input)
                return await self.async_step_add_device_dimensions()

        return self.async_show_form(
            step_id="add_device",
            data_schema=get_schema_step_zone(self.hass),
            errors=errors,
        )

    async def async_step_add_device_dimensions(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle dimensions for new zone."""
        if user_input is not None:
            self._zone_data.update(user_input)
            
            # Add zone to existing entry
            entry = self._get_entry()
            if entry:
                zone_id = str(uuid.uuid4())[:8]
                new_zones = dict(entry.data.get(CONF_ZONES, {}))
                new_zones[zone_id] = self._zone_data
                
                # Update entry data
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={CONF_ZONES: new_zones}
                )
                
                # Reload integration to pick up new zone
                await self.hass.config_entries.async_reload(entry.entry_id)
                
                return self.async_abort(reason="device_added")

            return self.async_abort(reason="unknown_error")

        return self.async_show_form(
            step_id="add_device_dimensions",
            data_schema=get_schema_step_dimensions(self.hass),
        )

    def _get_entry(self) -> config_entries.ConfigEntry | None:
        """Get existing config entry."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        return entries[0] if entries else None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HomePerformanceOptionsFlow:
        """Get the options flow for this handler."""
        return HomePerformanceOptionsFlow(config_entry)


class HomePerformanceOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Home Performance."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._selected_zone_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options - select zone to configure."""
        zones = self._config_entry.data.get(CONF_ZONES, {})
        
        if not zones:
            return self.async_abort(reason="no_zones")
        
        # Build zone selection options
        zone_options = []
        for zone_id, zone_data in zones.items():
            zone_name = zone_data.get(CONF_ZONE_NAME, zone_id)
            zone_options.append(
                selector.SelectOptionDict(value=zone_id, label=zone_name)
            )
        
        # Add delete option
        zone_options.append(
            selector.SelectOptionDict(value="__delete__", label="🗑️ Supprimer une zone")
        )

        if user_input is not None:
            selected = user_input.get("zone_select")
            if selected == "__delete__":
                return await self.async_step_delete_zone()
            
            self._selected_zone_id = selected
            return await self.async_step_configure_zone()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("zone_select"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=zone_options,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            description_placeholders={"count": str(len(zones))},
        )

    async def async_step_configure_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure a specific zone."""
        if self._selected_zone_id is None:
            return await self.async_step_init()
        
        zones = self._config_entry.data.get(CONF_ZONES, {})
        zone_data = zones.get(self._selected_zone_id, {})
        zone_name = zone_data.get(CONF_ZONE_NAME, "Zone")

        if user_input is not None:
            # Update zone configuration
            new_zones = dict(zones)
            new_zones[self._selected_zone_id] = {
                **zone_data,
                **user_input,
            }
            
            # Update entry
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={CONF_ZONES: new_zones}
            )
            
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="configure_zone",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HEATER_POWER,
                        default=zone_data.get(CONF_HEATER_POWER, 1000),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=100,
                            max=10000,
                            step=50,
                            unit_of_measurement="W",
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        CONF_SURFACE,
                        default=zone_data.get(CONF_SURFACE),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=500,
                            step=0.5,
                            unit_of_measurement="m²",
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        CONF_VOLUME,
                        default=zone_data.get(CONF_VOLUME),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=1500,
                            step=0.5,
                            unit_of_measurement="m³",
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        CONF_POWER_SENSOR,
                        default=zone_data.get(CONF_POWER_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="power",
                        )
                    ),
                    vol.Optional(
                        CONF_ENERGY_SENSOR,
                        default=zone_data.get(CONF_ENERGY_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="energy",
                        )
                    ),
                }
            ),
            description_placeholders={"zone_name": zone_name},
        )

    async def async_step_delete_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Delete a zone."""
        zones = self._config_entry.data.get(CONF_ZONES, {})
        
        if len(zones) <= 1:
            return self.async_abort(reason="cannot_delete_last_zone")
        
        # Build zone selection for deletion
        zone_options = []
        for zone_id, zone_data in zones.items():
            zone_name = zone_data.get(CONF_ZONE_NAME, zone_id)
            zone_options.append(
                selector.SelectOptionDict(value=zone_id, label=zone_name)
            )

        if user_input is not None:
            zone_to_delete = user_input.get("zone_to_delete")
            if zone_to_delete and zone_to_delete in zones:
                new_zones = {k: v for k, v in zones.items() if k != zone_to_delete}
                
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={CONF_ZONES: new_zones}
                )
                
                # Reload to remove entities
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                
                return self.async_abort(reason="zone_deleted")

        return self.async_show_form(
            step_id="delete_zone",
            data_schema=vol.Schema(
                {
                    vol.Required("zone_to_delete"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=zone_options,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )
