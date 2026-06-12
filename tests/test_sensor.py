"""Tests for Home Performance sensor / binary_sensor entities."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_performance.binary_sensor import (
    HeatingActiveSensor,
    WindowOpenSensor,
)
from custom_components.home_performance.const import (
    CONF_HEAT_SOURCE_TYPE,
    CONF_HEATER_POWER,
    CONF_HEATING_ENTITY,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_ZONE_NAME,
    DOMAIN,
    HEAT_SOURCE_ELECTRIC,
    MIN_DATA_HOURS,
)
from custom_components.home_performance.coordinator import HomePerformanceCoordinator
from custom_components.home_performance.sensor import (
    DataHoursSensor,
    EnergyPerformanceSensor,
    MeasuredEnergyDailySensor,
    ThermalLossCoefficientSensor,
)

ZONE = "Salon"


@pytest.fixture
def coordinator(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=ZONE,
        data={
            CONF_ZONE_NAME: ZONE,
            CONF_INDOOR_TEMP_SENSOR: "sensor.indoor",
            CONF_OUTDOOR_TEMP_SENSOR: "sensor.outdoor",
            CONF_HEATING_ENTITY: "switch.heating",
            CONF_HEATER_POWER: 1500.0,
            CONF_HEAT_SOURCE_TYPE: HEAT_SOURCE_ELECTRIC,
        },
    )
    entry.add_to_hass(hass)
    return HomePerformanceCoordinator(hass, entry)


class TestThermalLossCoefficientSensor:
    def test_native_value_none_without_data(self, coordinator):
        sensor = ThermalLossCoefficientSensor(coordinator, ZONE)
        coordinator.data = None
        assert sensor.native_value is None

    def test_native_value_rounded(self, coordinator):
        sensor = ThermalLossCoefficientSensor(coordinator, ZONE)
        coordinator.data = {"k_coefficient": 23.456}
        assert sensor.native_value == 23.5

    def test_heavy_attrs_unrecorded(self, coordinator):
        sensor = ThermalLossCoefficientSensor(coordinator, ZONE)
        assert "k_history_7d" in sensor._unrecorded_attributes
        assert "description" in sensor._unrecorded_attributes

    def test_reads_k_history_from_coordinator(self, coordinator):
        sensor = ThermalLossCoefficientSensor(coordinator, ZONE)
        coordinator.data = {
            "k_coefficient": 20.0,
            "k_history_7d": [{"date": "2025-01-01", "k": 20.0}],
        }
        attrs = sensor.extra_state_attributes
        assert attrs["k_history_7d"] == [{"date": "2025-01-01", "k": 20.0}]

    def test_unique_id_is_deterministic(self, coordinator):
        sensor = ThermalLossCoefficientSensor(coordinator, ZONE)
        assert sensor.unique_id == "home_performance_salon_k_coefficient"


class TestMeasuredEnergyDailySensor:
    def test_none_without_data(self, coordinator):
        sensor = MeasuredEnergyDailySensor(coordinator, ZONE)
        coordinator.data = None
        assert sensor.native_value is None

    def test_zero_is_kept_when_present(self, coordinator):
        sensor = MeasuredEnergyDailySensor(coordinator, ZONE)
        coordinator.data = {"measured_energy_daily_kwh": 0.0}
        assert sensor.native_value == 0.0

    def test_external_takes_priority(self, coordinator):
        sensor = MeasuredEnergyDailySensor(coordinator, ZONE)
        coordinator.data = {
            "external_energy_daily_kwh": 3.21,
            "measured_energy_daily_kwh": 9.99,
        }
        assert sensor.native_value == 3.21


class TestEnergyPerformanceSensor:
    def test_perf_memoized_consistent(self, coordinator):
        sensor = EnergyPerformanceSensor(coordinator, ZONE)
        coordinator.data = {
            "daily_energy_kwh": 2.0,
            "heater_power": 1500.0,
            "derived_power": None,
        }
        # native_value, icon and attributes all rely on the same memoized result
        level = sensor.native_value
        icon = sensor.icon
        attrs = sensor.extra_state_attributes
        assert level is not None
        assert icon.startswith("mdi:")
        assert "message" in attrs


class TestDiagnosticSensors:
    def test_data_hours_min_required_constant(self, coordinator):
        sensor = DataHoursSensor(coordinator, ZONE)
        coordinator.data = {"data_hours": 3.0, "samples_count": 10, "data_ready": False}
        attrs = sensor.extra_state_attributes
        assert attrs["min_hours_required"] == MIN_DATA_HOURS


class TestBinarySensors:
    def test_window_open_none_without_data(self, coordinator):
        sensor = WindowOpenSensor(coordinator, ZONE)
        coordinator.data = None
        assert sensor.is_on is None

    def test_heating_active_reflects_data(self, coordinator):
        sensor = HeatingActiveSensor(coordinator, ZONE)
        coordinator.data = {"heating_on": True}
        assert sensor.is_on is True
        coordinator.data = None
        assert sensor.is_on is None

    def test_binary_unique_id_deterministic(self, coordinator):
        sensor = WindowOpenSensor(coordinator, ZONE)
        assert sensor.unique_id == "home_performance_salon_window_open"
