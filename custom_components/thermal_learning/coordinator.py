"""DataUpdateCoordinator for Thermal Learning."""
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
    CONF_POWER_SENSOR,
    CONF_ZONE_NAME,
    CONF_VOLUME,
    DEFAULT_SCAN_INTERVAL,
)
from .models import ThermalModel, ThermalDataPoint

_LOGGER = logging.getLogger(__name__)


class ThermalLearningCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage thermal learning data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.zone_name: str = entry.data[CONF_ZONE_NAME]
        self.indoor_temp_sensor: str = entry.data[CONF_INDOOR_TEMP_SENSOR]
        self.outdoor_temp_sensor: str = entry.data[CONF_OUTDOOR_TEMP_SENSOR]
        self.heating_entity: str = entry.data[CONF_HEATING_ENTITY]
        self.power_sensor: str | None = entry.data.get(CONF_POWER_SENSOR)
        self.volume: float | None = entry.data.get(CONF_VOLUME)

        # Thermal model for learning (pass volume for G estimation if no power sensor)
        self.thermal_model = ThermalModel(self.zone_name, volume=self.volume)

        # Track last values for change detection
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
            power = self._get_power() if self.power_sensor else None

            # If sensors not available yet, return empty data without crashing
            if indoor_temp is None or outdoor_temp is None:
                _LOGGER.warning("Temperature sensors not available yet, skipping update")
                return {
                    "indoor_temp": None,
                    "outdoor_temp": None,
                    "heating_on": False,
                    "power": None,
                    "window_open": False,
                    "thermal_loss_coefficient": None,
                    "thermal_inertia": None,
                    "cooling_rate": None,
                    "time_to_target": None,
                    "learning_progress": 0,
                    "learning_complete": False,
                    "samples_count": 0,
                    "confidence": 0,
                }

            now = dt_util.utcnow().timestamp()

            # Create data point and add to model
            data_point = ThermalDataPoint(
                timestamp=now,
                indoor_temp=indoor_temp,
                outdoor_temp=outdoor_temp,
                heating_on=heating_on,
                power=power,
            )
            self.thermal_model.add_data_point(data_point)

            # Detect window open (rapid temperature drop)
            window_open = self._detect_window_open(indoor_temp, now)

            # Update tracking values
            self._last_indoor_temp = indoor_temp
            self._last_heating_state = heating_on
            self._last_update = now

            # Get computed values from model
            model_data = self.thermal_model.get_current_analysis()

            return {
                "indoor_temp": indoor_temp,
                "outdoor_temp": outdoor_temp,
                "heating_on": heating_on,
                "power": power,
                "window_open": window_open,
                "thermal_loss_coefficient": model_data.get("thermal_loss_coefficient"),
                "thermal_inertia": model_data.get("thermal_inertia"),
                "cooling_rate": model_data.get("cooling_rate"),
                "time_to_target": model_data.get("time_to_target"),
                "learning_progress": model_data.get("learning_progress", 0),
                "learning_complete": model_data.get("learning_complete", False),
                "samples_count": self.thermal_model.samples_count,
                "confidence": model_data.get("confidence", 0),
            }

        except Exception as err:
            _LOGGER.error("Error updating thermal learning data: %s", err)
            raise UpdateFailed(f"Error updating data: {err}") from err

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

    def _get_power(self) -> float | None:
        """Get power consumption from sensor."""
        if not self.power_sensor:
            return None
        state = self.hass.states.get(self.power_sensor)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

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

    def get_target_temperature(self) -> float | None:
        """Get target temperature from climate entity if available."""
        state = self.hass.states.get(self.heating_entity)
        if state and state.domain == "climate":
            return state.attributes.get("temperature")
        return None

    def can_calculate_thermal_loss(self) -> bool:
        """Check if thermal loss coefficient can be calculated.
        
        Returns True if power_sensor OR volume is configured.
        """
        return self.power_sensor is not None or self.volume is not None