"""Config flow for Home Performance integration."""
from __future__ import annotations

import logging
from typing import Any

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


def get_last_outdoor_temp_sensor(hass: HomeAssistant) -> str | None:
    """Get outdoor temp sensor from existing zones (for pre-filling)."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        outdoor_sensor = entry.data.get(CONF_OUTDOOR_TEMP_SENSOR)
        if outdoor_sensor:
            return outdoor_sensor
    return None


def get_schema_step_zone(hass: HomeAssistant, default_outdoor: str | None = None) -> vol.Schema:
    """Return schema for zone configuration step."""
    # Build outdoor temp field with or without default
    if default_outdoor:
        outdoor_field = vol.Required(CONF_OUTDOOR_TEMP_SENSOR, default=default_outdoor)
    else:
        outdoor_field = vol.Required(CONF_OUTDOOR_TEMP_SENSOR)

    return vol.Schema(
        {
            vol.Required(CONF_ZONE_NAME): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(CONF_INDOOR_TEMP_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            outdoor_field: selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Required(CONF_HEATING_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["climate", "switch", "input_boolean", "binary_sensor"])
            ),
            vol.Required(CONF_HEATER_POWER): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=100,
                    max=100000,
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


class HomePerformanceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Performance."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - zone configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that sensors exist and are available
            indoor_temp = user_input.get(CONF_INDOOR_TEMP_SENSOR)
            outdoor_temp = user_input.get(CONF_OUTDOOR_TEMP_SENSOR)
            heating = user_input.get(CONF_HEATING_ENTITY)

            # Check if entities exist
            if not self.hass.states.get(indoor_temp):
                errors[CONF_INDOOR_TEMP_SENSOR] = "entity_not_found"
            if not self.hass.states.get(outdoor_temp):
                errors[CONF_OUTDOOR_TEMP_SENSOR] = "entity_not_found"
            if not self.hass.states.get(heating):
                errors[CONF_HEATING_ENTITY] = "entity_not_found"

            # Validate heater power
            heater_power = user_input.get(CONF_HEATER_POWER)
            if not heater_power or heater_power <= 0:
                errors[CONF_HEATER_POWER] = "invalid_power"

            # Check if zone name is already used
            zone_name = user_input.get(CONF_ZONE_NAME, "").strip()
            zone_slug = zone_name.lower().replace(" ", "_")
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                existing_name = entry.data.get(CONF_ZONE_NAME, "")
                if existing_name.lower().replace(" ", "_") == zone_slug:
                    errors[CONF_ZONE_NAME] = "already_configured"
                    break

            if not errors:
                self._data.update(user_input)
                return await self.async_step_dimensions()

        # Get outdoor temp sensor from existing zones (for pre-filling)
        default_outdoor = get_last_outdoor_temp_sensor(self.hass)

        return self.async_show_form(
            step_id="user",
            data_schema=get_schema_step_zone(self.hass, default_outdoor),
            errors=errors,
            description_placeholders={"name": "Home Performance"},
        )

    async def async_step_dimensions(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the room dimensions configuration step."""
        if user_input is not None:
            self._data.update(user_input)

            # Create unique ID based on zone name
            zone_name = self._data[CONF_ZONE_NAME]
            await self.async_set_unique_id(
                f"home_performance_{zone_name.lower().replace(' ', '_')}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Home Performance - {zone_name}",
                data=self._data,
            )

        return self.async_show_form(
            step_id="dimensions",
            data_schema=get_schema_step_dimensions(self.hass),
        )

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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Clean up None values from optional fields
            cleaned_input = {k: v for k, v in user_input.items() if v is not None}
            return self.async_create_entry(title="", data=cleaned_input)

        # Get current values from data or options
        current = {**self._config_entry.data, **self._config_entry.options}

        # Build schema dynamically to avoid None defaults for NumberSelector
        schema_dict: dict[Any, Any] = {
            vol.Required(
                CONF_HEATER_POWER,
                default=current.get(CONF_HEATER_POWER, 1000),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=100,
                    max=100000,
                    step=50,
                    unit_of_measurement="W",
                    mode="box",
                )
            ),
        }

        # Surface - only set default if value exists (NumberSelector doesn't support None)
        surface_value = current.get(CONF_SURFACE)
        if surface_value is not None:
            schema_dict[vol.Optional(CONF_SURFACE, default=surface_value)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=500, step=0.5, unit_of_measurement="m²", mode="box"
                )
            )
        else:
            schema_dict[vol.Optional(CONF_SURFACE)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=500, step=0.5, unit_of_measurement="m²", mode="box"
                )
            )

        # Volume - only set default if value exists
        volume_value = current.get(CONF_VOLUME)
        if volume_value is not None:
            schema_dict[vol.Optional(CONF_VOLUME, default=volume_value)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=1500, step=0.5, unit_of_measurement="m³", mode="box"
                )
            )
        else:
            schema_dict[vol.Optional(CONF_VOLUME)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=1500, step=0.5, unit_of_measurement="m³", mode="box"
                )
            )

        # Power sensor - only set default if value exists (EntitySelector may not handle None in all HA versions)
        power_sensor_value = current.get(CONF_POWER_SENSOR)
        if power_sensor_value is not None:
            schema_dict[vol.Optional(CONF_POWER_SENSOR, default=power_sensor_value)] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="power",
                )
            )
        else:
            schema_dict[vol.Optional(CONF_POWER_SENSOR)] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="power",
                )
            )

        # Energy sensor - only set default if value exists
        energy_sensor_value = current.get(CONF_ENERGY_SENSOR)
        if energy_sensor_value is not None:
            schema_dict[vol.Optional(CONF_ENERGY_SENSOR, default=energy_sensor_value)] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="energy",
                )
            )
        else:
            schema_dict[vol.Optional(CONF_ENERGY_SENSOR)] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="energy",
                )
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
