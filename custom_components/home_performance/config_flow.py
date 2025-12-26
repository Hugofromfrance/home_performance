"""Config flow for Home Performance integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_ENERGY_SENSOR,
    CONF_HEAT_SOURCE_TYPE,
    CONF_HEATER_POWER,
    CONF_HEATING_ENTITY,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_NOTIFICATION_DELAY,
    CONF_NOTIFY_DEVICE,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_POWER_SENSOR,
    CONF_POWER_THRESHOLD,
    CONF_ROOM_ORIENTATION,
    CONF_SURFACE,
    CONF_VOLUME,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_NOTIFICATION_ENABLED,
    CONF_WINDOW_SENSOR,
    CONF_ZONE_NAME,
    DEFAULT_HEAT_SOURCE_TYPE,
    DEFAULT_NOTIFICATION_DELAY,
    DEFAULT_POWER_THRESHOLD,
    DOMAIN,
    HEAT_SOURCE_DISTRICT,
    HEAT_SOURCE_ELECTRIC,
    HEAT_SOURCE_GAS,
    HEAT_SOURCE_HEATPUMP,
    HEAT_SOURCES_REQUIRING_ENERGY,
    ORIENTATIONS,
)

_LOGGER = logging.getLogger(__name__)


def get_last_outdoor_temp_sensor(hass: HomeAssistant) -> str | None:
    """Get outdoor temp sensor from existing zones (for pre-filling)."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        outdoor_sensor = entry.data.get(CONF_OUTDOOR_TEMP_SENSOR)
        if outdoor_sensor:
            return outdoor_sensor
    return None


def get_last_weather_entity(hass: HomeAssistant) -> str | None:
    """Get weather entity from existing zones (for pre-filling)."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        # Check in options first, then data
        weather = entry.options.get(CONF_WEATHER_ENTITY) or entry.data.get(CONF_WEATHER_ENTITY)
        if weather:
            return weather
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
        vol.Required(CONF_HEAT_SOURCE_TYPE, default=DEFAULT_HEAT_SOURCE_TYPE): selector.SelectSelector(
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
    default_weather: str | None = None,
) -> vol.Schema:
    """Return schema for room dimensions and optional sensors configuration.

    Energy sensor is always optional. When configured, it provides the most
    accurate K coefficient calculation. When not configured, the integration
    falls back to power_sensor integration or heater_power estimation.
    """
    # Energy sensor: required for non-electric sources, optional for electric
    requires_energy = heat_source_type in HEAT_SOURCES_REQUIRING_ENERGY

    # Build weather entity field with or without default
    if default_weather:
        weather_field = vol.Optional(CONF_WEATHER_ENTITY, default=default_weather)
    else:
        weather_field = vol.Optional(CONF_WEATHER_ENTITY)

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
        vol.Optional(CONF_POWER_THRESHOLD, default=DEFAULT_POWER_THRESHOLD): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=1000,
                step=1,
                unit_of_measurement="W",
                mode="box",
            )
        ),
    }

    # Energy sensor field: required for non-electric, optional for electric
    if requires_energy:
        schema_dict[vol.Required(CONF_ENERGY_SENSOR)] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="energy",
            )
        )
    else:
        # Energy sensor is always optional but recommended for best accuracy
        schema_dict[vol.Optional(CONF_ENERGY_SENSOR)] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="energy",
            )
        )

    # Window sensor (optional)
    schema_dict[vol.Optional(CONF_WINDOW_SENSOR)] = selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="binary_sensor",
            device_class=["window", "door", "opening"],
        )
    )

    # Weather entity (optional)
    schema_dict[weather_field] = selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="weather",
        )
    )

    # Room orientation (optional)
    schema_dict[vol.Optional(CONF_ROOM_ORIENTATION)] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=ORIENTATIONS,
            mode=selector.SelectSelectorMode.DROPDOWN,
            translation_key="room_orientation",
        )
    )

    return vol.Schema(schema_dict)


class HomePerformanceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Performance."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
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

            # Check if zone name is already used (use slugify for consistent comparison)
            zone_name = user_input.get(CONF_ZONE_NAME, "").strip()
            zone_slug = slugify(zone_name, separator="_")
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                existing_name = entry.data.get(CONF_ZONE_NAME, "")
                if slugify(existing_name, separator="_") == zone_slug:
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

    async def async_step_dimensions(self, user_input: dict[str, Any] | None = None) -> FlowResult:
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

                # Create unique ID based on zone name (use slugify for special characters)
                zone_name = self._data[CONF_ZONE_NAME]
                zone_slug = slugify(zone_name, separator="_")
                await self.async_set_unique_id(f"home_performance_{zone_slug}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Home Performance - {zone_name}",
                    data=self._data,
                )

        # Get weather entity from existing zones (for pre-filling)
        default_weather = get_last_weather_entity(self.hass)

        return self.async_show_form(
            step_id="dimensions",
            data_schema=get_schema_step_dimensions(self.hass, heat_source_type, default_weather),
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

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
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

            # Validate power sensor if provided
            power_sensor = user_input.get(CONF_POWER_SENSOR)
            if power_sensor and not self.hass.states.get(power_sensor):
                errors[CONF_POWER_SENSOR] = "entity_not_found"

            # Validate energy sensor if provided (optional for all heat sources)
            energy_sensor = user_input.get(CONF_ENERGY_SENSOR)
            if energy_sensor and not self.hass.states.get(energy_sensor):
                errors[CONF_ENERGY_SENSOR] = "entity_not_found"

            # Validate window sensor if provided
            window_sensor = user_input.get(CONF_WINDOW_SENSOR)
            if window_sensor and not self.hass.states.get(window_sensor):
                errors[CONF_WINDOW_SENSOR] = "entity_not_found"

            if not errors:
                # Keep None values to allow removing sensors (override data with options)
                # But remove keys that are None AND not in current config (truly optional)
                cleaned_input = {}
                for k, v in user_input.items():
                    if v is not None:
                        cleaned_input[k] = v
                    elif k in current and current[k] is not None:
                        # User cleared a previously set value - explicitly set to None
                        # This allows removing a power_sensor or energy_sensor
                        cleaned_input[k] = None
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
            schema_dict[
                vol.Required(
                    CONF_HEATER_POWER,
                    default=heater_power_value or 1000,
                )
            ] = selector.NumberSelector(
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
                    selector.NumberSelectorConfig(min=100, max=100000, step=50, unit_of_measurement="W", mode="box")
                )
            else:
                schema_dict[vol.Optional(CONF_HEATER_POWER)] = selector.NumberSelector(
                    selector.NumberSelectorConfig(min=100, max=100000, step=50, unit_of_measurement="W", mode="box")
                )

        # Surface - only set default if value exists (NumberSelector doesn't support None)
        surface_value = current.get(CONF_SURFACE)
        if surface_value is not None:
            schema_dict[vol.Optional(CONF_SURFACE, default=surface_value)] = selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=500, step=0.5, unit_of_measurement="m²", mode="box")
            )
        else:
            schema_dict[vol.Optional(CONF_SURFACE)] = selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=500, step=0.5, unit_of_measurement="m²", mode="box")
            )

        # Volume - only set default if value exists
        volume_value = current.get(CONF_VOLUME)
        if volume_value is not None:
            schema_dict[vol.Optional(CONF_VOLUME, default=volume_value)] = selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=1500, step=0.5, unit_of_measurement="m³", mode="box")
            )
        else:
            schema_dict[vol.Optional(CONF_VOLUME)] = selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=1500, step=0.5, unit_of_measurement="m³", mode="box")
            )

        # Power sensor - only set default if value exists (EntitySelector doesn't handle None)
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

        # Energy sensor - required for non-electric sources, optional for electric
        energy_sensor_value = current.get(CONF_ENERGY_SENSOR)
        if heat_source_type in HEAT_SOURCES_REQUIRING_ENERGY:
            schema_dict[
                vol.Required(
                    CONF_ENERGY_SENSOR,
                    default=energy_sensor_value,
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="energy",
                )
            )
        elif energy_sensor_value is not None:
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

        # Window sensor - only set default if value exists
        window_sensor_value = current.get(CONF_WINDOW_SENSOR)
        if window_sensor_value is not None:
            schema_dict[vol.Optional(CONF_WINDOW_SENSOR, default=window_sensor_value)] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="binary_sensor",
                    device_class=["window", "door", "opening"],
                )
            )
        else:
            schema_dict[vol.Optional(CONF_WINDOW_SENSOR)] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="binary_sensor",
                    device_class=["window", "door", "opening"],
                )
            )

        # === NOTIFICATION OPTIONS ===
        # Enable window notifications
        notification_enabled = current.get(CONF_WINDOW_NOTIFICATION_ENABLED, False)
        schema_dict[vol.Optional(CONF_WINDOW_NOTIFICATION_ENABLED, default=notification_enabled)] = (
            selector.BooleanSelector()
        )

        # Notify device - only show if notifications are or will be enabled
        notify_device_value = current.get(CONF_NOTIFY_DEVICE)
        if notify_device_value is not None:
            schema_dict[vol.Optional(CONF_NOTIFY_DEVICE, default=notify_device_value)] = selector.DeviceSelector(
                selector.DeviceSelectorConfig(filter=selector.DeviceFilterSelectorConfig(integration="mobile_app"))
            )
        else:
            schema_dict[vol.Optional(CONF_NOTIFY_DEVICE)] = selector.DeviceSelector(
                selector.DeviceSelectorConfig(filter=selector.DeviceFilterSelectorConfig(integration="mobile_app"))
            )

        # Notification delay
        notification_delay = current.get(CONF_NOTIFICATION_DELAY, DEFAULT_NOTIFICATION_DELAY)
        schema_dict[vol.Optional(CONF_NOTIFICATION_DELAY, default=notification_delay)] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=30,
                step=1,
                unit_of_measurement="min",
                mode="slider",
            )
        )

        # === WEATHER OPTIONS ===
        # Weather entity - shared between zones, pre-fill from other zones if not set
        weather_entity_value = current.get(CONF_WEATHER_ENTITY)
        if not weather_entity_value:
            weather_entity_value = get_last_weather_entity(self.hass)
        if weather_entity_value is not None:
            schema_dict[vol.Optional(CONF_WEATHER_ENTITY, default=weather_entity_value)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            )
        else:
            schema_dict[vol.Optional(CONF_WEATHER_ENTITY)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            )

        # Room orientation
        room_orientation_value = current.get(CONF_ROOM_ORIENTATION)
        if room_orientation_value is not None:
            schema_dict[vol.Optional(CONF_ROOM_ORIENTATION, default=room_orientation_value)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=ORIENTATIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="room_orientation",
                )
            )
        else:
            schema_dict[vol.Optional(CONF_ROOM_ORIENTATION)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=ORIENTATIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="room_orientation",
                )
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
