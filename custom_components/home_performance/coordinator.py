"""DataUpdateCoordinator for Home Performance."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_INDOOR_TEMP_SENSOR,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_HEATING_ENTITY,
    CONF_HEATER_POWER,
    CONF_ZONE_NAME,
    CONF_SURFACE,
    CONF_VOLUME,
    DEFAULT_SCAN_INTERVAL,
)
from .models import ThermalLossModel, ThermalDataPoint

_LOGGER = logging.getLogger(__name__)


class HomePerformanceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage home performance data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.zone_name: str = entry.data[CONF_ZONE_NAME]
        self.indoor_temp_sensor: str = entry.data[CONF_INDOOR_TEMP_SENSOR]
        self.outdoor_temp_sensor: str = entry.data[CONF_OUTDOOR_TEMP_SENSOR]
        self.heating_entity: str = entry.data[CONF_HEATING_ENTITY]
        self.heater_power: float = entry.data[CONF_HEATER_POWER]
        self.surface: float | None = entry.data.get(CONF_SURFACE)
        self.volume: float | None = entry.data.get(CONF_VOLUME)

        # Thermal model
        self.thermal_model = ThermalLossModel(
            zone_name=self.zone_name,
            heater_power=self.heater_power,
            surface=self.surface,
            volume=self.volume,
        )

        # Track for window detection
        self._last_indoor_temp: float | None = None
        self._last_heating_state: bool | None = None
        self._last_update: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.zone_name}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors and update thermal model."""
        try:
            # Get current sensor values
            indoor_temp = self._get_temperature(self.indoor_temp_sensor)
            outdoor_temp = self._get_temperature(self.outdoor_temp_sensor)
            heating_on = self._get_heating_state()

            # If sensors not available yet, return empty data
            if indoor_temp is None or outdoor_temp is None:
                _LOGGER.warning(
                    "Temperature sensors not available yet, skipping update"
                )
                return self._get_empty_data()

            now = dt_util.utcnow().timestamp()

            # Create data point and add to model
            data_point = ThermalDataPoint(
                timestamp=now,
                indoor_temp=indoor_temp,
                outdoor_temp=outdoor_temp,
                heating_on=heating_on,
            )
            self.thermal_model.add_data_point(data_point)

            # Detect window open (rapid temperature drop)
            window_open = self._detect_window_open(indoor_temp, now)

            # Update tracking values
            self._last_indoor_temp = indoor_temp
            self._last_heating_state = heating_on
            self._last_update = now

            # Get analysis from model
            analysis = self.thermal_model.get_analysis()

            return {
                # Current values
                "indoor_temp": indoor_temp,
                "outdoor_temp": outdoor_temp,
                "heating_on": heating_on,
                "delta_t": indoor_temp - outdoor_temp,
                "window_open": window_open,
                # Calculated coefficients
                "k_coefficient": analysis.get("k_coefficient"),
                "k_per_m2": analysis.get("k_per_m2"),
                "k_per_m3": analysis.get("k_per_m3"),
                # Period data
                "heating_hours": analysis.get("heating_hours"),
                "heating_ratio": analysis.get("heating_ratio"),
                "avg_delta_t": analysis.get("avg_delta_t"),
                "daily_energy_kwh": analysis.get("daily_energy_kwh"),
                # Status
                "data_hours": analysis.get("data_hours"),
                "samples_count": analysis.get("samples_count"),
                "data_ready": analysis.get("data_ready"),
                # Configuration
                "heater_power": self.heater_power,
                "surface": self.surface,
                "volume": self.volume,
                # Insulation rating
                "insulation_rating": self.thermal_model.get_insulation_rating(),
            }

        except Exception as err:
            _LOGGER.error("Error updating home performance data: %s", err)
            raise UpdateFailed(f"Error updating data: {err}") from err

    def _get_empty_data(self) -> dict[str, Any]:
        """Return empty data structure."""
        return {
            "indoor_temp": None,
            "outdoor_temp": None,
            "heating_on": False,
            "delta_t": None,
            "window_open": False,
            "k_coefficient": None,
            "k_per_m2": None,
            "k_per_m3": None,
            "heating_hours": None,
            "heating_ratio": None,
            "avg_delta_t": None,
            "daily_energy_kwh": None,
            "data_hours": 0,
            "samples_count": 0,
            "data_ready": False,
            "heater_power": self.heater_power,
            "surface": self.surface,
            "volume": self.volume,
            "insulation_rating": None,
        }

    def _get_temperature(self, entity_id: str) -> float | None:
        """Get temperature from sensor entity."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _get_heating_state(self) -> bool:
        """Get heating state from climate/switch entity."""
        state = self.hass.states.get(self.heating_entity)
        if state is None:
            return False

        # Handle climate entities
        if state.domain == "climate":
            hvac_action = state.attributes.get("hvac_action")
            if hvac_action:
                return hvac_action == "heating"
            return state.state not in ("off", STATE_UNAVAILABLE, STATE_UNKNOWN)

        # Handle switch/input_boolean
        return state.state == STATE_ON

    def _detect_window_open(self, current_temp: float, now: float) -> bool:
        """Detect if window is likely open based on rapid temperature drop."""
        if self._last_indoor_temp is None or self._last_update is None:
            return False

        time_delta = now - self._last_update
        if time_delta <= 0:
            return False

        # Calculate temperature change rate (°C per minute)
        temp_change = current_temp - self._last_indoor_temp
        rate_per_minute = (temp_change / time_delta) * 60

        # If temperature drops more than 0.5°C per minute while heating is on
        # or more than 1°C per minute regardless, likely window open
        if self._last_heating_state and rate_per_minute < -0.5:
            return True
        if rate_per_minute < -1.0:
            return True

        return False
