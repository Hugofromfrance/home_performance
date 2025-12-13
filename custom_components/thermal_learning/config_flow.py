"""Config flow for Thermal Learning integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_HEATING_ENTITY,
    CONF_POWER_SENSOR,
    CONF_ZONE_NAME,
    CONF_SURFACE,
    CONF_VOLUME,
)

_LOGGER = logging.getLogger(__name__)


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
        }
    )


def get_schema_step_optional(hass: HomeAssistant) -> vol.Schema:
    """Return schema for optional configuration step."""
    return vol.Schema(
        {
            vol.Optional(CONF_POWER_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            vol.Optional(CONF_SURFACE): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=500, step=0.5, unit_of_measurement="m²", mode="box"
                )
            ),
            vol.Optional(CONF_VOLUME): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=1500, step=0.5, unit_of_measurement="m³", mode="box"
                )
            ),
        }
    )


class ThermalLearningConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Thermal Learning."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
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

            if not errors:
                self._data.update(user_input)
                return await self.async_step_optional()

        return self.async_show_form(
            step_id="user",
            data_schema=get_schema_step_zone(self.hass),
            errors=errors,
            description_placeholders={"name": "Thermal Learning"},
        )

    async def async_step_optional(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the optional configuration step."""
        if user_input is not None:
            self._data.update(user_input)

            # Create unique ID based on zone name
            zone_name = self._data[CONF_ZONE_NAME]
            await self.async_set_unique_id(f"thermal_learning_{zone_name.lower().replace(' ', '_')}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Thermal Learning - {zone_name}",
                data=self._data,
            )

        return self.async_show_form(
            step_id="optional",
            data_schema=get_schema_step_optional(self.hass),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ThermalLearningOptionsFlow:
        """Get the options flow for this handler."""
        return ThermalLearningOptionsFlow()


class ThermalLearningOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Thermal Learning."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_POWER_SENSOR,
                        default=self.config_entry.data.get(CONF_POWER_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor", device_class="power")
                    ),
                    vol.Optional(
                        CONF_SURFACE,
                        default=self.config_entry.data.get(CONF_SURFACE),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=500, step=0.5, unit_of_measurement="m²", mode="box"
                        )
                    ),
                    vol.Optional(
                        CONF_VOLUME,
                        default=self.config_entry.data.get(CONF_VOLUME),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1, max=1500, step=0.5, unit_of_measurement="m³", mode="box"
                        )
                    ),
                }
            ),
        )