"""Tests for the Home Performance config & options flow.

Focus on the validation fixed during the audit: the energy sensor must be
required based on the heat source selected *in the form*, not the stored one.
"""

from __future__ import annotations

import pytest

from custom_components.home_performance.config_flow import (
    HomePerformanceConfigFlow,
    HomePerformanceOptionsFlow,
    validate_entity,
)
from custom_components.home_performance.const import (
    CONF_ENERGY_SENSOR,
    CONF_HEAT_SOURCE_TYPE,
    CONF_HEATER_POWER,
    CONF_HEATING_ENTITY,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_POWER_SENSOR,
    CONF_ZONE_NAME,
    DOMAIN,
    HEAT_SOURCE_ELECTRIC,
    HEAT_SOURCE_HEATPUMP,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

INDOOR = "sensor.indoor"
OUTDOOR = "sensor.outdoor"
HEATING = "switch.heating"
ENERGY = "sensor.energy"


def _electric_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Salon",
        data={
            CONF_ZONE_NAME: "Salon",
            CONF_INDOOR_TEMP_SENSOR: INDOOR,
            CONF_OUTDOOR_TEMP_SENSOR: OUTDOOR,
            CONF_HEATING_ENTITY: HEATING,
            CONF_HEATER_POWER: 1500.0,
            CONF_HEAT_SOURCE_TYPE: HEAT_SOURCE_ELECTRIC,
        },
    )


def _make_options_flow(hass, entry) -> HomePerformanceOptionsFlow:
    entry.add_to_hass(hass)
    flow = HomePerformanceOptionsFlow(entry)
    flow.hass = hass
    return flow


class TestOptionsEnergyValidation:
    async def test_switch_to_heatpump_requires_energy_sensor(self, hass):
        """Switching to heat pump without an energy sensor must error."""
        flow = _make_options_flow(hass, _electric_entry())
        result = await flow.async_step_init(
            {
                CONF_HEAT_SOURCE_TYPE: HEAT_SOURCE_HEATPUMP,
                # no energy sensor provided
            }
        )
        assert result["type"] == "form"
        assert result["errors"].get(CONF_ENERGY_SENSOR) == "energy_sensor_required"

    async def test_heatpump_with_energy_sensor_passes(self, hass):
        """Providing the energy sensor clears the requirement error."""
        hass.states.async_set(ENERGY, "12.0", {"unit_of_measurement": "kWh"})
        flow = _make_options_flow(hass, _electric_entry())
        result = await flow.async_step_init(
            {
                CONF_HEAT_SOURCE_TYPE: HEAT_SOURCE_HEATPUMP,
                CONF_ENERGY_SENSOR: ENERGY,
            }
        )
        # No energy_sensor_required error -> proceeds to the heat pump options step
        if result["type"] == "form":
            assert "energy_sensor_required" not in (result.get("errors") or {}).values()

    async def test_unknown_energy_sensor_reports_not_found(self, hass):
        flow = _make_options_flow(hass, _electric_entry())
        result = await flow.async_step_init(
            {
                CONF_HEAT_SOURCE_TYPE: HEAT_SOURCE_HEATPUMP,
                CONF_ENERGY_SENSOR: "sensor.does_not_exist",
            }
        )
        assert result["type"] == "form"
        assert result["errors"].get(CONF_ENERGY_SENSOR) == "entity_not_found"

    async def test_electric_requires_positive_power(self, hass):
        flow = _make_options_flow(hass, _electric_entry())
        result = await flow.async_step_init(
            {
                CONF_HEAT_SOURCE_TYPE: HEAT_SOURCE_ELECTRIC,
                CONF_HEATER_POWER: 0,
            }
        )
        assert result["type"] == "form"
        assert result["errors"].get(CONF_HEATER_POWER) == "invalid_power"

    async def test_unknown_power_sensor_reports_not_found(self, hass):
        flow = _make_options_flow(hass, _electric_entry())
        result = await flow.async_step_init(
            {
                CONF_HEAT_SOURCE_TYPE: HEAT_SOURCE_ELECTRIC,
                CONF_HEATER_POWER: 1500,
                CONF_POWER_SENSOR: "sensor.missing_power",
            }
        )
        assert result["type"] == "form"
        assert result["errors"].get(CONF_POWER_SENSOR) == "entity_not_found"


class TestValidateEntity:
    """The shared validate_entity helper."""

    def test_none_or_empty_is_ok(self, hass):
        assert validate_entity(hass, None) is None
        assert validate_entity(hass, "") is None

    def test_missing_entity(self, hass):
        assert validate_entity(hass, "sensor.nope") == "entity_not_found"

    def test_unavailable_entity_rejected(self, hass):
        hass.states.async_set("sensor.flaky", "unavailable")
        assert validate_entity(hass, "sensor.flaky") == "entity_not_found"

    def test_unknown_entity_rejected(self, hass):
        hass.states.async_set("sensor.flaky2", "unknown")
        assert validate_entity(hass, "sensor.flaky2") == "entity_not_found"

    def test_usable_entity_ok(self, hass):
        hass.states.async_set("sensor.ok", "21.5", {"unit_of_measurement": "°C"})
        assert validate_entity(hass, "sensor.ok") is None


class TestConfigUserFlow:
    """Drive the config flow directly (avoids pulling integration dependencies)."""

    def _flow(self, hass) -> HomePerformanceConfigFlow:
        flow = HomePerformanceConfigFlow()
        flow.hass = hass
        return flow

    async def test_user_step_entity_not_found(self, hass):
        flow = self._flow(hass)
        result = await flow.async_step_user(
            {
                CONF_ZONE_NAME: "Bureau",
                CONF_INDOOR_TEMP_SENSOR: "sensor.missing_in",
                CONF_OUTDOOR_TEMP_SENSOR: "sensor.missing_out",
                CONF_HEATING_ENTITY: "switch.missing",
                CONF_HEAT_SOURCE_TYPE: HEAT_SOURCE_ELECTRIC,
                CONF_HEATER_POWER: 1500,
            }
        )
        assert result["type"] == "form"
        assert result["errors"].get(CONF_INDOOR_TEMP_SENSOR) == "entity_not_found"

    async def test_user_step_duplicate_zone(self, hass):
        existing = _electric_entry()
        existing.add_to_hass(hass)
        hass.states.async_set(INDOOR, "20", {"unit_of_measurement": "°C"})
        hass.states.async_set(OUTDOOR, "5", {"unit_of_measurement": "°C"})
        hass.states.async_set(HEATING, "on")

        flow = self._flow(hass)
        result = await flow.async_step_user(
            {
                CONF_ZONE_NAME: "Salon",  # same slug as existing
                CONF_INDOOR_TEMP_SENSOR: INDOOR,
                CONF_OUTDOOR_TEMP_SENSOR: OUTDOOR,
                CONF_HEATING_ENTITY: HEATING,
                CONF_HEAT_SOURCE_TYPE: HEAT_SOURCE_ELECTRIC,
                CONF_HEATER_POWER: 1500,
            }
        )
        assert result["type"] == "form"
        assert result["errors"].get(CONF_ZONE_NAME) == "already_configured"
