"""Tests for the Home Performance coordinator.

These focus on the behaviours fixed/added during the audit:
- force-save does not crash and persists (shutdown regression),
- reset services clear state and persist,
- the update cycle produces the expected data dict,
- the midnight reset drops the external-energy baseline,
- the storage migration invalidates the biased pre-v2 24h K data.
"""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_performance.const import (
    CONF_HEAT_SOURCE_TYPE,
    CONF_HEATER_POWER,
    CONF_HEATING_ENTITY,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_ZONE_NAME,
    DOMAIN,
    HEAT_SOURCE_ELECTRIC,
)
from custom_components.home_performance.coordinator import (
    STORAGE_VERSION,
    HomePerformanceCoordinator,
    HomePerformanceStore,
)

INDOOR = "sensor.indoor"
OUTDOOR = "sensor.outdoor"
HEATING = "switch.heating"


def _make_entry() -> MockConfigEntry:
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


@pytest.fixture
def coordinator(hass):
    """Build a coordinator wired to a few mock source sensors."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    hass.states.async_set(INDOOR, "20.0", {"unit_of_measurement": "°C"})
    hass.states.async_set(OUTDOOR, "5.0", {"unit_of_measurement": "°C"})
    hass.states.async_set(HEATING, "on")
    return HomePerformanceCoordinator(hass, entry)


class TestForceSave:
    async def test_force_save_does_not_crash(self, coordinator):
        """Regression: async_save_data(force=True) used to raise TypeError."""
        await coordinator.async_save_data(force=True)
        stored = await coordinator._store.async_load()
        assert stored is not None
        assert "thermal_model" in stored

    async def test_shutdown_persists(self, coordinator):
        """async_shutdown finalizes and saves without raising."""
        await coordinator.async_shutdown()
        stored = await coordinator._store.async_load()
        assert stored is not None


class TestResetPersistence:
    async def test_reset_all_persists_cleared_state(self, coordinator):
        """reset_all_data + save => reloaded model has no history/points."""
        # Seed some state then reset
        coordinator._measured_energy_total_kwh = 5.0
        coordinator.reset_all_data()
        await coordinator.async_save_data(force=True)

        assert coordinator._measured_energy_total_kwh == 0.0

        # A fresh coordinator loading the same store sees the cleared data
        fresh = HomePerformanceCoordinator(coordinator.hass, coordinator.entry)
        await fresh._async_load_data()
        assert fresh.thermal_model.samples_count == 0
        assert fresh.thermal_model.history_days_count == 0

    async def test_reset_history_clears_history(self, coordinator):
        coordinator.reset_history()
        assert coordinator.thermal_model.history_days_count == 0


class TestUpdateCycle:
    async def test_update_returns_expected_keys(self, coordinator):
        data = await coordinator._async_update_data()
        for key in (
            "indoor_temp",
            "outdoor_temp",
            "heating_on",
            "delta_t",
            "k_coefficient",
            "k_history_7d",
            "data_hours",
        ):
            assert key in data
        assert data["indoor_temp"] == 20.0
        assert data["outdoor_temp"] == 5.0
        assert data["delta_t"] == pytest.approx(15.0)
        assert isinstance(data["k_history_7d"], list)

    async def test_update_handles_unavailable_sensors(self, hass):
        """When sensors aren't available yet, restored data is returned (no crash)."""
        entry = _make_entry()
        entry.add_to_hass(hass)
        # No source states set at all
        coord = HomePerformanceCoordinator(hass, entry)
        data = await coord._async_update_data()
        assert data["indoor_temp"] is None
        assert "k_history_7d" in data


class TestMidnightReset:
    def test_external_energy_baseline_dropped(self, coordinator):
        """The external-energy baseline resets at midnight to avoid bad deltas."""
        coordinator._last_external_energy = 42.0
        coordinator._last_daily_reset_date = "1970-01-01"  # force a "new day"
        import homeassistant.util.dt as dt_util

        coordinator._check_daily_reset(dt_util.now())
        assert coordinator._last_external_energy is None


class TestStorageMigration:
    async def test_migration_drops_biased_24h_data(self, hass):
        store = HomePerformanceStore(hass, STORAGE_VERSION, f"{DOMAIN}.salon")
        old = {
            "thermal_model": {
                "data_points": [{"timestamp": 1.0, "indoor_temp": 20, "outdoor_temp": 5, "heating_on": True}],
                "last_point": {"timestamp": 1.0, "indoor_temp": 20, "outdoor_temp": 5, "heating_on": True},
                "k_coefficient": 99.0,
                "k_coefficient_7d": 25.0,
                "daily_history": [{"date": "2025-01-01"}],
            }
        }
        migrated = await store._async_migrate_func(1, 1, old)
        model = migrated["thermal_model"]
        assert model["data_points"] == []
        assert model["last_point"] is None
        assert model["k_coefficient"] is None
        # 7-day data and history are preserved
        assert model["k_coefficient_7d"] == 25.0
        assert model["daily_history"] == [{"date": "2025-01-01"}]
