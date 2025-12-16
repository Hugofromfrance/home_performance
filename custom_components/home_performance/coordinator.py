"""DataUpdateCoordinator for Home Performance."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
    DEFAULT_SCAN_INTERVAL,
)
from .models import ThermalLossModel, ThermalDataPoint

_LOGGER = logging.getLogger(__name__)

# Storage version and save interval
STORAGE_VERSION = 1
SAVE_INTERVAL_SECONDS = 300  # Save every 5 minutes


class HomePerformanceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage home performance data for a single zone."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        
        # Merge data and options (options override data)
        config = {**entry.data, **entry.options}
        
        # Zone configuration
        self.zone_name: str = config[CONF_ZONE_NAME]
        self.indoor_temp_sensor: str = config[CONF_INDOOR_TEMP_SENSOR]
        self.outdoor_temp_sensor: str = config[CONF_OUTDOOR_TEMP_SENSOR]
        self.heating_entity: str = config[CONF_HEATING_ENTITY]
        self.heater_power: float = config[CONF_HEATER_POWER]
        self.surface: float | None = config.get(CONF_SURFACE)
        self.volume: float | None = config.get(CONF_VOLUME)
        self.power_sensor: str | None = config.get(CONF_POWER_SENSOR)
        self.energy_sensor: str | None = config.get(CONF_ENERGY_SENSOR)

        _LOGGER.info(
            "HomePerformance coordinator initialized for %s: power_sensor=%s, energy_sensor=%s",
            self.zone_name, self.power_sensor, self.energy_sensor
        )

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

        # Energy integration from power sensor
        self._last_power_update: float | None = None
        self._last_power_value: float | None = None
        self._measured_energy_total_kwh: float = 0.0
        self._measured_energy_daily_kwh: float = 0.0
        self._last_daily_reset_date: str | None = None
        self._daily_reset_datetime: Any = None  # datetime for utility meter compatibility

        # Persistence
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{self.zone_name.lower().replace(' ', '_')}",
        )
        self._last_save_time: float = 0
        self._data_loaded: bool = False

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.zone_name}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def async_config_entry_first_refresh(self) -> None:
        """Load persisted data before first refresh."""
        await self._async_load_data()
        await super().async_config_entry_first_refresh()

    async def _async_load_data(self) -> None:
        """Load persisted data from storage."""
        try:
            data = await self._store.async_load()
            if data:
                _LOGGER.info("Loading persisted data for zone %s", self.zone_name)
                
                # Restore thermal model
                if "thermal_model" in data:
                    self.thermal_model.from_dict(data["thermal_model"])
                
                # Restore energy counters
                if "measured_energy_total_kwh" in data:
                    self._measured_energy_total_kwh = data["measured_energy_total_kwh"]
                if "measured_energy_daily_kwh" in data:
                    self._measured_energy_daily_kwh = data["measured_energy_daily_kwh"]
                if "last_daily_reset_date" in data:
                    self._last_daily_reset_date = data["last_daily_reset_date"]
                if "daily_reset_datetime" in data:
                    # Restore as string, will be converted on next update
                    pass
                
                # Restore tracking values
                if "last_indoor_temp" in data:
                    self._last_indoor_temp = data["last_indoor_temp"]
                if "last_heating_state" in data:
                    self._last_heating_state = data["last_heating_state"]
                if "last_power_value" in data:
                    self._last_power_value = data["last_power_value"]
                
                self._data_loaded = True
                _LOGGER.info(
                    "Restored data for %s: %.1fh of thermal data, %.3f kWh total energy",
                    self.zone_name,
                    self.thermal_model.data_hours,
                    self._measured_energy_total_kwh,
                )
            else:
                _LOGGER.info("No persisted data found for zone %s", self.zone_name)
        except Exception as err:
            _LOGGER.error("Error loading persisted data: %s", err)

    async def async_save_data(self) -> None:
        """Save data to persistent storage."""
        try:
            data = {
                "thermal_model": self.thermal_model.to_dict(),
                "measured_energy_total_kwh": self._measured_energy_total_kwh,
                "measured_energy_daily_kwh": self._measured_energy_daily_kwh,
                "last_daily_reset_date": self._last_daily_reset_date,
                "last_indoor_temp": self._last_indoor_temp,
                "last_heating_state": self._last_heating_state,
                "last_power_value": self._last_power_value,
            }
            await self._store.async_save(data)
            self._last_save_time = dt_util.utcnow().timestamp()
            _LOGGER.debug("Saved data for zone %s", self.zone_name)
        except Exception as err:
            _LOGGER.error("Error saving data: %s", err)

    async def _async_maybe_save(self) -> None:
        """Save data if enough time has passed since last save."""
        now = dt_util.utcnow().timestamp()
        if now - self._last_save_time >= SAVE_INTERVAL_SECONDS:
            await self.async_save_data()

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

            # Update measured energy from power sensor (if configured)
            measured_power = self._update_measured_energy(now)

            # Get external energy sensor value (if configured)
            external_energy = self._get_external_energy()

            # Periodically save data to persistent storage
            await self._async_maybe_save()

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
                # Cumulative energy (for Energy Dashboard)
                "total_energy_kwh": analysis.get("total_energy_kwh"),
                # Measured energy (from power sensor)
                "measured_power_w": measured_power,
                "measured_energy_daily_kwh": self._measured_energy_daily_kwh,
                "measured_energy_total_kwh": self._measured_energy_total_kwh,
                "daily_reset_datetime": self._daily_reset_datetime,
                "power_sensor_configured": self.power_sensor is not None,
                # External energy sensor (if configured, takes priority)
                "external_energy_daily_kwh": external_energy,
                "energy_sensor_configured": self.energy_sensor is not None,
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
            "total_energy_kwh": 0.0,
            "external_energy_daily_kwh": None,
            "energy_sensor_configured": self.energy_sensor is not None,
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

    def _get_external_energy(self) -> float | None:
        """Get energy value from external energy sensor (if configured)."""
        if self.energy_sensor is None:
            return None
        
        state = self.hass.states.get(self.energy_sensor)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _get_heating_state(self) -> bool:
        """Get heating state from power sensor (exclusive) or climate/switch entity.
        
        If a power sensor is configured, ONLY use it to detect actual heating:
        - Power > 50W = heating is active
        - Power unavailable = no heating (don't fallback to switch)
        
        This is critical for radiators with internal thermostats where
        the switch is always ON but actual heating depends on thermostat.
        """
        # If power sensor is configured, use it EXCLUSIVELY (no fallback)
        if self.power_sensor:
            power_state = self.hass.states.get(self.power_sensor)
            if power_state and power_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    power_w = float(power_state.state)
                    is_heating = power_w > 50
                    _LOGGER.debug(
                        "Heating detection via power sensor %s: %.1fW -> heating=%s",
                        self.power_sensor, power_w, is_heating
                    )
                    return is_heating
                except (ValueError, TypeError) as err:
                    _LOGGER.warning("Could not parse power sensor value: %s", err)
            
            # Power sensor configured but unavailable -> assume not heating
            # DO NOT fallback to switch (it's always ON for thermostatic radiators)
            _LOGGER.debug(
                "Power sensor %s unavailable, assuming not heating (no fallback to switch)",
                self.power_sensor
            )
            return False
        
        # No power sensor configured -> use climate/switch entity state
        _LOGGER.debug("No power sensor configured, using heating entity state")
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
        is_on = state.state == STATE_ON
        _LOGGER.debug("Heating detection via switch %s: state=%s -> heating=%s",
                      self.heating_entity, state.state, is_on)
        return is_on

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

    def _update_measured_energy(self, now: float) -> float | None:
        """
        Update measured energy by integrating power over time.
        
        Uses trapezoidal integration for better accuracy.
        Automatically resets daily counter at midnight.
        """
        if self.power_sensor is None:
            return None

        # Check for daily reset (midnight)
        now_dt = dt_util.now()
        today = now_dt.strftime("%Y-%m-%d")
        if self._last_daily_reset_date != today:
            _LOGGER.debug(
                "Resetting daily energy counter for %s (new day: %s)",
                self.zone_name,
                today,
            )
            self._measured_energy_daily_kwh = 0.0
            self._last_daily_reset_date = today
            # Store the reset datetime for utility meter compatibility
            self._daily_reset_datetime = now_dt.replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        # Get current power value
        power_state = self.hass.states.get(self.power_sensor)
        if power_state is None or power_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None

        try:
            current_power = float(power_state.state)
        except (ValueError, TypeError):
            return None

        # If we have a previous reading, integrate
        if self._last_power_update is not None and self._last_power_value is not None:
            time_delta_hours = (now - self._last_power_update) / 3600  # Convert to hours
            
            # Trapezoidal integration: average of last and current power
            avg_power_w = (self._last_power_value + current_power) / 2
            energy_kwh = (avg_power_w * time_delta_hours) / 1000  # W*h to kWh
            
            # Add to counters
            self._measured_energy_daily_kwh += energy_kwh
            self._measured_energy_total_kwh += energy_kwh

        # Update tracking values
        self._last_power_update = now
        self._last_power_value = current_power

        return current_power
