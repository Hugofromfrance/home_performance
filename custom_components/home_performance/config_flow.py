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
    CONF_POWER_THRESHOLD,
    CONF_HEAT_SOURCE_TYPE,
    DEFAULT_POWER_THRESHOLD,
    DEFAULT_HEAT_SOURCE_TYPE,
    HEAT_SOURCE_ELECTRIC,
    HEAT_SOURCE_HEATPUMP,
    HEAT_SOURCE_GAS,
    HEAT_SOURCE_DISTRICT,
)

_LOGGER = logging.getLogger(__name__)


def get_last_outdoor_temp_sensor(hass: HomeAssistant) -> str | None:
    """Get outdoor temp sensor from existing zones (for pre-filling)."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        outdoor_sensor = entry.data.get(CONF_OUTDOOR_TEMP_SENSOR)
        if outdoor_sensor:
            return outdoor_sensor
    return None


def get_schema_step_zone(
    hass: HomeAssistant,
    default_outdoor: str | None = None,
    heat_source_type: str = HEAT_SOURCE_ELECTRIC,
) -> vol.Schema:
    """Return schema for zone configuration step."""
    # Build outdoor temp field with or without default
    if default_outdoor:
        outdoor_field = vol.Required(CONF_OUTDOOR_TEMP_SENSOR, default=default_outdoor)
    else:
        outdoor_field = vol.Required(CONF_OUTDOOR_TEMP_SENSOR)

    # Heat source type selector
    heat_source_options = [
        selector.SelectOptionDict(value=HEAT_SOURCE_ELECTRIC, label="Electric"),
        selector.SelectOptionDict(value=HEAT_SOURCE_HEATPUMP, label="Heat pump"),
        selector.SelectOptionDict(value=HEAT_SOURCE_GAS, label="Gas"),
        selector.SelectOptionDict(value=HEAT_SOURCE_DISTRICT, label="District heating"),
    ]

    schema_dict = {
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
        vol.Required(
            CONF_HEAT_SOURCE_TYPE, default=DEFAULT_HEAT_SOURCE_TYPE
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=heat_source_options,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }

    # Heater power: required for electric, optional for others
    if heat_source_type == HEAT_SOURCE_ELECTRIC:
        schema_dict[vol.Required(CONF_HEATER_POWER)] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=100,
                max=100000,
                step=50,
                unit_of_measurement="W",
                mode="box",
            )
        )
    else:
        schema_dict[vol.Optional(CONF_HEATER_POWER)] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=100,
                max=100000,
                step=50,
                unit_of_measurement="W",
                mode="box",
            )
        )

    return vol.Schema(schema_dict)


def get_schema_step_dimensions(
    hass: HomeAssistant,
    heat_source_type: str = HEAT_SOURCE_ELECTRIC,
) -> vol.Schema:
    """Return schema for room dimensions and optional sensors configuration.

    Energy sensor is always optional. When configured, it provides the most
    accurate K coefficient calculation. When not configured, the integration
    falls back to power_sensor integration or heater_power estimation.
    """
    schema_dict: dict[Any, Any] = {
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
        vol.Optional(
            CONF_POWER_THRESHOLD, default=DEFAULT_POWER_THRESHOLD
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=1000,
                step=1,
                unit_of_measurement="W",
                mode="box",
            )
        ),
        # Energy sensor is always optional but recommended for best accuracy
        vol.Optional(CONF_ENERGY_SENSOR): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="energy",
            )
        ),
    }

    return vol.Schema(schema_dict)


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

            # Get heat source type (default to electric for backward compat)
            heat_source_type = user_input.get(CONF_HEAT_SOURCE_TYPE, HEAT_SOURCE_ELECTRIC)

            # Validate heater power - required only for electric
            heater_power = user_input.get(CONF_HEATER_POWER)
            if heat_source_type == HEAT_SOURCE_ELECTRIC:
                if not heater_power or heater_power <= 0:
                    errors[CONF_HEATER_POWER] = "invalid_power"
            elif heater_power is not None and heater_power <= 0:
                # Optional but if provided must be valid
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

        # Get heat source type from current data (for re-display after error)
        current_heat_source = self._data.get(CONF_HEAT_SOURCE_TYPE, HEAT_SOURCE_ELECTRIC)

        return self.async_show_form(
            step_id="user",
            data_schema=get_schema_step_zone(self.hass, default_outdoor, current_heat_source),
            errors=errors,
            description_placeholders={"name": "Home Performance"},
        )

    async def async_step_dimensions(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the room dimensions configuration step."""
        errors: dict[str, str] = {}
        heat_source_type = self._data.get(CONF_HEAT_SOURCE_TYPE, HEAT_SOURCE_ELECTRIC)

        if user_input is not None:
            # Validate energy sensor if provided (optional for all heat sources)
            energy_sensor = user_input.get(CONF_ENERGY_SENSOR)
            if energy_sensor and not self.hass.states.get(energy_sensor):
                errors[CONF_ENERGY_SENSOR] = "entity_not_found"

            # Validate power sensor if provided
            power_sensor = user_input.get(CONF_POWER_SENSOR)
            if power_sensor and not self.hass.states.get(power_sensor):
                errors[CONF_POWER_SENSOR] = "entity_not_found"

            if not errors:
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
            data_schema=get_schema_step_dimensions(self.hass, heat_source_type),
            errors=errors,
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
        errors: dict[str, str] = {}

        # Get current values from data or options
        current = {**self._config_entry.data, **self._config_entry.options}
        heat_source_type = current.get(CONF_HEAT_SOURCE_TYPE, HEAT_SOURCE_ELECTRIC)

        if user_input is not None:
            # Validate based on heat source type
            new_heat_source = user_input.get(CONF_HEAT_SOURCE_TYPE, heat_source_type)

            # Validate heater power for electric (required)
            if new_heat_source == HEAT_SOURCE_ELECTRIC:
                heater_power = user_input.get(CONF_HEATER_POWER)
                if not heater_power or heater_power <= 0:
                    errors[CONF_HEATER_POWER] = "invalid_power"

            # Validate energy sensor if provided (optional for all heat sources)
            energy_sensor = user_input.get(CONF_ENERGY_SENSOR)
            if energy_sensor and not self.hass.states.get(energy_sensor):
                errors[CONF_ENERGY_SENSOR] = "entity_not_found"

            # Validate power sensor if provided
            power_sensor = user_input.get(CONF_POWER_SENSOR)
            if power_sensor and not self.hass.states.get(power_sensor):
                errors[CONF_POWER_SENSOR] = "entity_not_found"

            if not errors:
                # Clean up None values from optional fields
                cleaned_input = {k: v for k, v in user_input.items() if v is not None}
                return self.async_create_entry(title="", data=cleaned_input)

        # Heat source type selector
        heat_source_options = [
            selector.SelectOptionDict(value=HEAT_SOURCE_ELECTRIC, label="Electric"),
            selector.SelectOptionDict(value=HEAT_SOURCE_HEATPUMP, label="Heat pump"),
            selector.SelectOptionDict(value=HEAT_SOURCE_GAS, label="Gas"),
            selector.SelectOptionDict(value=HEAT_SOURCE_DISTRICT, label="District heating"),
        ]

        # Build schema dynamically
        schema_dict: dict[Any, Any] = {
            vol.Required(
                CONF_HEAT_SOURCE_TYPE,
                default=heat_source_type,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=heat_source_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }

        # Heater power - required for electric, optional for others
        heater_power_value = current.get(CONF_HEATER_POWER)
        if heat_source_type == HEAT_SOURCE_ELECTRIC:
            schema_dict[vol.Required(
                CONF_HEATER_POWER,
                default=heater_power_value or 1000,
            )] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=100,
                    max=100000,
                    step=50,
                    unit_of_measurement="W",
                    mode="box",
                )
            )
        else:
            if heater_power_value is not None:
                schema_dict[vol.Optional(CONF_HEATER_POWER, default=heater_power_value)] = selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=100, max=100000, step=50, unit_of_measurement="W", mode="box"
                    )
                )
            else:
                schema_dict[vol.Optional(CONF_HEATER_POWER)] = selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=100, max=100000, step=50, unit_of_measurement="W", mode="box"
                    )
                )

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

        # Power sensor - only set default if value exists
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

        # Energy sensor - always optional but recommended for best accuracy
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

        # Power threshold - always show with default
        power_threshold_value = current.get(CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD)
        schema_dict[vol.Optional(CONF_POWER_THRESHOLD, default=power_threshold_value)] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=1000,
                step=1,
                unit_of_measurement="W",
                mode="box",
            )
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
