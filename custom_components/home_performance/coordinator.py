"""DataUpdateCoordinator for Home Performance."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter
import time

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
    DEFAULT_POWER_THRESHOLD,
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
        self.power_threshold: float = config.get(CONF_POWER_THRESHOLD) or DEFAULT_POWER_THRESHOLD

        _LOGGER.info(
            "HomePerformance coordinator initialized for zone '%s': "
            "indoor_temp=%s, outdoor_temp=%s, heating_entity=%s, "
            "power_sensor=%s, energy_sensor=%s, heater_power=%sW",
            self.zone_name,
            self.indoor_temp_sensor,
            self.outdoor_temp_sensor,
            self.heating_entity,
            self.power_sensor,
            self.energy_sensor,
            self.heater_power
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

        # Energy integration from power sensor (measured)
        self._last_power_update: float | None = None
        self._last_power_value: float | None = None
        self._measured_energy_total_kwh: float = 0.0
        self._measured_energy_daily_kwh: float = 0.0

        # Daily counters (reset at midnight) - for minuit-minuit consistency
        self._last_daily_reset_date: str | None = None
        self._daily_reset_datetime: Any = None  # datetime for utility meter compatibility
        self._estimated_energy_daily_kwh: float = 0.0  # Estimated energy since midnight
        self._heating_seconds_daily: float = 0.0  # Heating time since midnight
        self._delta_t_sum_daily: float = 0.0  # Sum of ΔT for daily average
        self._delta_t_count_daily: int = 0  # Count of samples for daily average

        # Real-time heating tracking (event-driven for precision)
        self._heating_start_time: float | None = None  # Timestamp when heating started
        self._is_heating_realtime: bool = False  # Current real-time heating state
        self._power_listener_unsub: Any = None  # Listener unsubscribe callback

        # Real-time window detection (event-driven for fast response)
        self._temp_listener_unsub: Any = None  # Temperature listener unsubscribe
        self._last_temp_value: float | None = None  # Last temperature value
        self._last_temp_time: float | None = None  # Last temperature timestamp
        self._window_open_realtime: bool = False  # Real-time window open state
        self._window_open_since: float | None = None  # Timestamp when window was detected open
        self._consecutive_drops: int = 0  # Count of consecutive temperature drops

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
        self._setup_power_listener()
        self._setup_temperature_listener()
        await super().async_config_entry_first_refresh()

    def _setup_power_listener(self) -> None:
        """Set up real-time listener for power sensor changes."""
        if not self.power_sensor:
            _LOGGER.debug("[%s] No power sensor configured, skipping real-time listener", self.zone_name)
            return

        @callback
        def _async_power_state_changed(event: Event) -> None:
            """Handle power sensor state changes in real-time."""
            new_state = event.data.get("new_state")
            old_state = event.data.get("old_state")

            if new_state is None:
                return

            # Parse power values
            try:
                new_power = float(new_state.state) if new_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN) else 0.0
            except (ValueError, TypeError):
                new_power = 0.0

            try:
                old_power = float(old_state.state) if old_state and old_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN) else 0.0
            except (ValueError, TypeError):
                old_power = 0.0

            now = time.time()
            is_heating_now = new_power > self.power_threshold
            was_heating = old_power > self.power_threshold

            _LOGGER.debug(
                "[%s] Power sensor changed: %.1fW -> %.1fW (heating: %s -> %s)",
                self.zone_name, old_power, new_power, was_heating, is_heating_now
            )

            # Heating started
            if is_heating_now and not self._is_heating_realtime:
                self._heating_start_time = now
                self._is_heating_realtime = True
                _LOGGER.info("[%s] 🔥 Heating started (real-time detection)", self.zone_name)

            # Heating stopped
            elif not is_heating_now and self._is_heating_realtime:
                if self._heating_start_time is not None:
                    duration = now - self._heating_start_time
                    self._heating_seconds_daily += duration
                    # Also update estimated energy
                    energy_kwh = (self.heater_power / 1000) * (duration / 3600)
                    self._estimated_energy_daily_kwh += energy_kwh
                    _LOGGER.info(
                        "[%s] ❄️ Heating stopped (real-time). Duration: %.1fs (%.2f min), Energy: %.4f kWh",
                        self.zone_name, duration, duration / 60, energy_kwh
                    )
                self._heating_start_time = None
                self._is_heating_realtime = False

        # Subscribe to power sensor state changes
        self._power_listener_unsub = async_track_state_change_event(
            self.hass,
            [self.power_sensor],
            _async_power_state_changed,
        )
        _LOGGER.info("[%s] ✅ Real-time power listener set up for %s", self.zone_name, self.power_sensor)

    def _setup_temperature_listener(self) -> None:
        """Set up real-time listener for indoor temperature changes (window detection)."""

        @callback
        def _async_temp_state_changed(event: Event) -> None:
            """Handle indoor temperature changes in real-time for window detection."""
            new_state = event.data.get("new_state")

            if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                return

            try:
                new_temp = float(new_state.state)

                # Convert to Celsius if needed (for consistent rate calculations)
                unit = new_state.attributes.get("unit_of_measurement", UnitOfTemperature.CELSIUS)
                if unit == UnitOfTemperature.FAHRENHEIT:
                    new_temp = TemperatureConverter.convert(
                        new_temp,
                        UnitOfTemperature.FAHRENHEIT,
                        UnitOfTemperature.CELSIUS
                    )
            except (ValueError, TypeError):
                return

            now = time.time()

            # Check for rapid temperature drop (window open detection)
            # Improved algorithm to reduce false positives with fast-cycling systems (e.g., US furnaces)
            if self._last_temp_value is not None and self._last_temp_time is not None:
                time_delta = now - self._last_temp_time
                if time_delta > 0:
                    temp_change = new_temp - self._last_temp_value
                    rate_per_minute = (temp_change / time_delta) * 60

                    # Thresholds (in °C/min):
                    # - 0.7°C/min while heating (was 0.5, more tolerant for fast-cycling systems)
                    # - 1.2°C/min regardless (was 1.0, accounts for natural cooling after furnace off)
                    DROP_THRESHOLD_HEATING = -0.7
                    DROP_THRESHOLD_ANY = -1.2
                    CONSECUTIVE_DROPS_REQUIRED = 2  # Need 2+ consecutive readings to confirm

                    was_window_open = self._window_open_realtime
                    is_rapid_drop = (
                        (self._is_heating_realtime and rate_per_minute < DROP_THRESHOLD_HEATING)
                        or rate_per_minute < DROP_THRESHOLD_ANY
                    )

                    if is_rapid_drop:
                        self._consecutive_drops += 1
                        if self._consecutive_drops >= CONSECUTIVE_DROPS_REQUIRED:
                            if not was_window_open:
                                self._window_open_realtime = True
                                self._window_open_since = now
                                _LOGGER.warning(
                                    "[%s] 🪟 Window OPEN detected! Temp drop: %.2f°C/min (heating: %s)",
                                    self.zone_name, abs(rate_per_minute), self._is_heating_realtime
                                )
                    elif rate_per_minute > 0.1:
                        # Temperature rising = window likely closed
                        self._consecutive_drops = 0
                        if was_window_open:
                            _LOGGER.info("[%s] 🪟 Window CLOSED (temperature rising)", self.zone_name)
                        self._window_open_realtime = False
                        self._window_open_since = None
                    elif abs(rate_per_minute) < 0.2:
                        # Temperature stable (not dropping fast) - close window after 5 min
                        self._consecutive_drops = 0
                        if was_window_open and self._window_open_since:
                            minutes_open = (now - self._window_open_since) / 60
                            if minutes_open > 5:
                                _LOGGER.info("[%s] 🪟 Window CLOSED (temperature stabilized after %.1f min)", self.zone_name, minutes_open)
                                self._window_open_realtime = False
                                self._window_open_since = None

            # Update tracking values
            self._last_temp_value = new_temp
            self._last_temp_time = now

        # Subscribe to indoor temperature sensor changes
        self._temp_listener_unsub = async_track_state_change_event(
            self.hass,
            [self.indoor_temp_sensor],
            _async_temp_state_changed,
        )
        _LOGGER.info("[%s] ✅ Real-time temperature listener set up for %s", self.zone_name, self.indoor_temp_sensor)

    async def async_shutdown(self) -> None:
        """Clean up when coordinator is shut down."""
        # Unsubscribe from power sensor listener
        if self._power_listener_unsub:
            self._power_listener_unsub()
            self._power_listener_unsub = None
            _LOGGER.debug("[%s] Power listener unsubscribed", self.zone_name)

        # Unsubscribe from temperature sensor listener
        if self._temp_listener_unsub:
            self._temp_listener_unsub()
            self._temp_listener_unsub = None
            _LOGGER.debug("[%s] Temperature listener unsubscribed", self.zone_name)

        # Finalize any ongoing heating session
        if self._is_heating_realtime and self._heating_start_time is not None:
            duration = time.time() - self._heating_start_time
            self._heating_seconds_daily += duration
            energy_kwh = (self.heater_power / 1000) * (duration / 3600)
            self._estimated_energy_daily_kwh += energy_kwh
            _LOGGER.info("[%s] Finalized heating session on shutdown: %.1fs", self.zone_name, duration)

        # Save data before shutdown
        await self.async_save_data(force=True)

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

                # Restore daily counters (minuit-minuit)
                if "estimated_energy_daily_kwh" in data:
                    self._estimated_energy_daily_kwh = data["estimated_energy_daily_kwh"]
                if "heating_seconds_daily" in data:
                    self._heating_seconds_daily = data["heating_seconds_daily"]
                if "delta_t_sum_daily" in data:
                    self._delta_t_sum_daily = data["delta_t_sum_daily"]
                if "delta_t_count_daily" in data:
                    self._delta_t_count_daily = data["delta_t_count_daily"]

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
                # Daily counters (minuit-minuit)
                "estimated_energy_daily_kwh": self._estimated_energy_daily_kwh,
                "heating_seconds_daily": self._heating_seconds_daily,
                "delta_t_sum_daily": self._delta_t_sum_daily,
                "delta_t_count_daily": self._delta_t_count_daily,
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

            # If sensors not available yet, return restored data (not empty!)
            if indoor_temp is None or outdoor_temp is None:
                _LOGGER.debug(
                    "[%s] Temperature sensors not available yet, returning restored data",
                    self.zone_name
                )
                return self._get_restored_data()

            now = dt_util.utcnow().timestamp()
            now_dt = dt_util.now()

            # Check for daily reset (midnight)
            self._check_daily_reset(now_dt)

            # Create data point and add to model (for K coefficient - still uses rolling 24h)
            data_point = ThermalDataPoint(
                timestamp=now,
                indoor_temp=indoor_temp,
                outdoor_temp=outdoor_temp,
                heating_on=heating_on,
            )
            self.thermal_model.add_data_point(data_point)

            # Detect window open (combine real-time detection with polling fallback)
            window_open = self._window_open_realtime or self._detect_window_open(indoor_temp, now)

            # Update daily counters (minuit-minuit)
            delta_t = indoor_temp - outdoor_temp
            self._update_daily_counters(now, heating_on, delta_t)

            # Update tracking values
            self._last_indoor_temp = indoor_temp
            self._last_heating_state = heating_on
            self._last_update = now

            # Get analysis from model (for K coefficient - rolling 24h)
            analysis = self.thermal_model.get_analysis()

            # Update measured energy from power sensor (if configured)
            measured_power = self._update_measured_energy(now)

            # Get external energy sensor value (if configured)
            external_energy = self._get_external_energy()

            # Calculate daily values (minuit-minuit)
            # Include ongoing heating session in the total
            heating_seconds = self._heating_seconds_daily
            if self._is_heating_realtime and self._heating_start_time is not None:
                # Add time from current ongoing heating session
                heating_seconds += (now - self._heating_start_time)
            heating_hours_daily = heating_seconds / 3600

            # ΔT moyen : utiliser la valeur 24h glissante du modèle thermique
            # (plus stable que le calcul depuis minuit)
            avg_delta_t_rolling = analysis.get("avg_delta_t") or delta_t

            # Periodically save data to persistent storage
            await self._async_maybe_save()

            return {
                # Current values
                "indoor_temp": indoor_temp,
                "outdoor_temp": outdoor_temp,
                "heating_on": heating_on,
                "delta_t": delta_t,
                "window_open": window_open,
                # Calculated coefficients
                "k_coefficient": analysis.get("k_coefficient"),  # Prefers 7-day stable K
                "k_coefficient_24h": analysis.get("k_coefficient_24h"),  # Real-time 24h K
                "k_coefficient_7d": analysis.get("k_coefficient_7d"),  # Stable 7-day K
                "k_per_m2": analysis.get("k_per_m2"),
                "k_per_m3": analysis.get("k_per_m3"),
                # Usage data (24h rolling window)
                "heating_hours": heating_hours_daily,
                "heating_ratio": heating_hours_daily / 24 if heating_hours_daily else 0,
                "avg_delta_t": avg_delta_t_rolling,
                "daily_energy_kwh": self._estimated_energy_daily_kwh,
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
                "storage_loaded": self._data_loaded,
                # 7-day history status
                "history_days": analysis.get("history_days", 0),
                "history_has_valid_k": analysis.get("history_has_valid_k", False),
                # Configuration
                "heater_power": self.heater_power,
                "surface": self.surface,
                "volume": self.volume,
                "power_threshold": self.power_threshold,
                # Insulation rating (with season/inference support)
                "insulation_rating": self.thermal_model.get_insulation_rating(),
                "insulation_status": self.thermal_model.get_insulation_status(),
                "last_valid_k": self.thermal_model.last_valid_k,
            }

        except Exception as err:
            _LOGGER.error("Error updating home performance data: %s", err)
            raise UpdateFailed(f"Error updating data: {err}") from err

    def _get_empty_data(self) -> dict[str, Any]:
        """Return empty data structure."""
        return {
            "indoor_temp": None,
            "outdoor_temp": None,
            "heating_on": self._is_heating_realtime,
            "delta_t": None,
            "window_open": self._window_open_realtime,
            "k_coefficient": None,
            "k_coefficient_24h": None,
            "k_coefficient_7d": None,
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
            "storage_loaded": self._data_loaded,
            "history_days": 0,
            "history_has_valid_k": False,
            "heater_power": self.heater_power,
            "surface": self.surface,
            "volume": self.volume,
            "power_threshold": self.power_threshold,
            "insulation_rating": None,
            "insulation_status": {
                "status": "waiting_data",
                "rating": None,
                "k_value": None,
                "k_source": None,
                "season": "heating_season",
                "message": "Data collection in progress",
                "temp_stable": None,
            },
            "last_valid_k": None,
        }

    def _get_restored_data(self) -> dict[str, Any]:
        """Return data from restored thermal model (when sensors not yet available)."""
        analysis = self.thermal_model.get_analysis()

        # Calculate restored heating values
        # Include ongoing heating session in the total
        heating_seconds = self._heating_seconds_daily
        if self._is_heating_realtime and self._heating_start_time is not None:
            heating_seconds += (time.time() - self._heating_start_time)
        heating_hours_daily = heating_seconds / 3600

        # ΔT moyen : utiliser la valeur 24h glissante du modèle thermique
        avg_delta_t_rolling = analysis.get("avg_delta_t")

        return {
            # Current values - not available yet
            "indoor_temp": None,
            "outdoor_temp": None,
            "heating_on": self._is_heating_realtime,
            "delta_t": None,
            "window_open": self._window_open_realtime,
            # Restored coefficients from model
            "k_coefficient": analysis.get("k_coefficient"),  # Prefers 7-day stable K
            "k_coefficient_24h": analysis.get("k_coefficient_24h"),
            "k_coefficient_7d": analysis.get("k_coefficient_7d"),
            "k_per_m2": analysis.get("k_per_m2"),
            "k_per_m3": analysis.get("k_per_m3"),
            # Restored usage data (24h rolling window)
            "heating_hours": heating_hours_daily,
            "heating_ratio": heating_hours_daily / 24 if heating_hours_daily else 0,
            "avg_delta_t": avg_delta_t_rolling,
            "daily_energy_kwh": self._estimated_energy_daily_kwh,
            "total_energy_kwh": analysis.get("total_energy_kwh"),
            # Measured energy
            "measured_power_w": None,
            "measured_energy_daily_kwh": self._measured_energy_daily_kwh,
            "measured_energy_total_kwh": self._measured_energy_total_kwh,
            "daily_reset_datetime": self._daily_reset_datetime,
            "power_sensor_configured": self.power_sensor is not None,
            "external_energy_daily_kwh": None,
            "energy_sensor_configured": self.energy_sensor is not None,
            # Restored status
            "data_hours": analysis.get("data_hours"),
            "samples_count": analysis.get("samples_count"),
            "data_ready": analysis.get("data_ready"),
            "storage_loaded": self._data_loaded,
            # 7-day history status
            "history_days": analysis.get("history_days", 0),
            "history_has_valid_k": analysis.get("history_has_valid_k", False),
            # Configuration
            "heater_power": self.heater_power,
            "surface": self.surface,
            "volume": self.volume,
            "power_threshold": self.power_threshold,
            # Restored insulation rating (with season/inference support)
            "insulation_rating": self.thermal_model.get_insulation_rating(),
            "insulation_status": self.thermal_model.get_insulation_status(),
            "last_valid_k": self.thermal_model.last_valid_k,
        }

    def _check_daily_reset(self, now_dt) -> None:
        """Check and perform daily reset at midnight.

        IMPORTANT: Archives yesterday's data to 7-day history BEFORE resetting counters.
        This ensures the insulation rating remains stable across midnight.
        """
        today = now_dt.strftime("%Y-%m-%d")
        if self._last_daily_reset_date != today:
            _LOGGER.warning(
                "[%s] 🌙 MIDNIGHT RESET TRIGGERED - previous_date=%s, new_date=%s, samples=%d",
                self.zone_name, self._last_daily_reset_date, today, self._delta_t_count_daily
            )

            # Archive yesterday's data BEFORE resetting (if we have data)
            if self._last_daily_reset_date and self._delta_t_count_daily > 0:
                _LOGGER.warning(
                    "[%s] 📦 ARCHIVING day %s with %d samples",
                    self.zone_name, self._last_daily_reset_date, self._delta_t_count_daily
                )
                self._archive_daily_data(self._last_daily_reset_date)
            else:
                _LOGGER.warning(
                    "[%s] ⚠️ SKIPPING archive - last_date=%s, samples=%d",
                    self.zone_name, self._last_daily_reset_date, self._delta_t_count_daily
                )

            _LOGGER.info(
                "[%s] 🌙 Daily reset (new day: %s)",
                self.zone_name, today
            )
            # Reset all daily counters
            self._measured_energy_daily_kwh = 0.0
            self._estimated_energy_daily_kwh = 0.0
            self._heating_seconds_daily = 0.0
            self._delta_t_sum_daily = 0.0
            self._delta_t_count_daily = 0
            self._last_daily_reset_date = today
            self._daily_reset_datetime = now_dt.replace(
                hour=0, minute=0, second=0, microsecond=0
            )

    def _archive_daily_data(self, date: str) -> None:
        """Archive a day's data to the thermal model's 7-day history.

        Called at midnight before resetting daily counters.

        Args:
            date: The date (YYYY-MM-DD) of the data to archive
        """
        # Calculate averages
        avg_delta_t = (
            self._delta_t_sum_daily / self._delta_t_count_daily
            if self._delta_t_count_daily > 0 else 0.0
        )

        # Get average temps from the last aggregation or estimate
        analysis = self.thermal_model.get_analysis()
        avg_indoor = 0.0
        avg_outdoor = 0.0

        # Try to get from model's last aggregation
        if hasattr(self.thermal_model, '_last_aggregation') and self.thermal_model._last_aggregation:
            agg = self.thermal_model._last_aggregation
            avg_indoor = agg.avg_indoor_temp
            avg_outdoor = agg.avg_outdoor_temp

        heating_hours = self._heating_seconds_daily / 3600

        # Get current K_7j BEFORE adding today's data (this is the score we had today)
        current_k_7d = self.thermal_model.k_coefficient_7d

        _LOGGER.info(
            "[%s] 📦 Archiving daily data for %s: heating=%.1fh, ΔT=%.1f°C, energy=%.2f kWh, samples=%d, k_7d=%.1f",
            self.zone_name, date, heating_hours, avg_delta_t,
            self._estimated_energy_daily_kwh, self._delta_t_count_daily,
            current_k_7d if current_k_7d else 0.0
        )

        # Add to thermal model history (with the K_7j score we had at this moment)
        self.thermal_model.add_daily_summary(
            date=date,
            heating_hours=heating_hours,
            avg_delta_t=avg_delta_t,
            energy_kwh=self._estimated_energy_daily_kwh,
            avg_indoor_temp=avg_indoor,
            avg_outdoor_temp=avg_outdoor,
            sample_count=self._delta_t_count_daily,
            k_7d=current_k_7d,
        )

        # Log history status after archiving
        history_count = len(self.thermal_model.daily_history)
        new_k_7d = self.thermal_model.k_coefficient_7d
        _LOGGER.warning(
            "[%s] ✅ ARCHIVE COMPLETE - history_days=%d, k_7d=%s W/°C",
            self.zone_name, history_count, f"{new_k_7d:.1f}" if new_k_7d else "None"
        )

    def reset_history(self) -> None:
        """Reset the 7-day history (manual reset service).

        Use this after insulation work or to clear anomalous data.
        """
        _LOGGER.info("[%s] 🔄 Manual history reset requested", self.zone_name)
        self.thermal_model.clear_history()

    def _update_daily_counters(self, now: float, heating_on: bool, delta_t: float) -> None:
        """Update daily counters (minuit-minuit)."""
        if self._last_update is not None:
            time_delta_seconds = now - self._last_update
            time_delta_hours = time_delta_seconds / 3600

            # Update heating time and energy ONLY if no power_sensor (no real-time listener)
            # When power_sensor is configured, the real-time listener handles this more precisely
            if not self.power_sensor:
                if self._last_heating_state:
                    self._heating_seconds_daily += time_delta_seconds
                    # Update estimated energy (power * time)
                    energy_kwh = (self.heater_power / 1000) * time_delta_hours
                    self._estimated_energy_daily_kwh += energy_kwh

        # Update ΔT average (always done via polling)
        self._delta_t_sum_daily += delta_t
        self._delta_t_count_daily += 1

    def _get_temperature(self, entity_id: str) -> float | None:
        """Get temperature from sensor entity, converted to Celsius.

        All internal calculations use Celsius. This handles users with
        Fahrenheit-configured Home Assistant instances.
        """
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            temp_value = float(state.state)

            # Get the unit from the sensor's attributes (more reliable than HA config)
            unit = state.attributes.get("unit_of_measurement", UnitOfTemperature.CELSIUS)

            # Convert to Celsius if needed
            if unit == UnitOfTemperature.FAHRENHEIT:
                temp_value = TemperatureConverter.convert(
                    temp_value,
                    UnitOfTemperature.FAHRENHEIT,
                    UnitOfTemperature.CELSIUS
                )

            return temp_value
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
                    is_heating = power_w > self.power_threshold
                    _LOGGER.debug(
                        "[%s] Heating detection via power sensor %s: %.1fW (threshold: %.0fW) -> heating=%s",
                        self.zone_name, self.power_sensor, power_w, self.power_threshold, is_heating
                    )
                    return is_heating
                except (ValueError, TypeError) as err:
                    _LOGGER.warning("[%s] Could not parse power sensor value: %s", self.zone_name, err)

            # Power sensor configured but unavailable -> assume not heating
            # DO NOT fallback to switch (it's always ON for thermostatic radiators)
            _LOGGER.debug(
                "[%s] Power sensor %s unavailable (state=%s), assuming not heating",
                self.zone_name, self.power_sensor, power_state.state if power_state else "None"
            )
            return False

        # No power sensor configured -> use climate/switch entity state
        _LOGGER.debug("[%s] No power sensor, using heating entity state", self.zone_name)
        state = self.hass.states.get(self.heating_entity)
        if state is None:
            _LOGGER.warning("[%s] Heating entity %s not found", self.zone_name, self.heating_entity)
            return False

        # Get domain from entity_id
        domain = self.heating_entity.split(".")[0]

        # Handle climate entities
        if domain == "climate":
            hvac_action = state.attributes.get("hvac_action")
            hvac_mode = state.state  # heat, cool, heat_cool, off, etc.
            _LOGGER.debug(
                "[%s] Heating via climate %s: hvac_mode=%s, hvac_action=%s",
                self.zone_name, self.heating_entity, hvac_mode, hvac_action
            )
            # Check hvac_action first (most reliable - indicates actual heating activity)
            if hvac_action:
                return hvac_action in ("heating", "heat")
            # Fallback to hvac_mode (less reliable - only indicates mode, not activity)
            return hvac_mode in ("heat", "heat_cool") and hvac_mode not in ("off", STATE_UNAVAILABLE, STATE_UNKNOWN)

        # Handle switch/input_boolean
        is_on = state.state == STATE_ON
        _LOGGER.debug("[%s] Heating via switch %s: state=%s -> heating=%s",
                      self.zone_name, self.heating_entity, state.state, is_on)
        return is_on

    def _detect_window_open(self, current_temp: float, now: float) -> bool:
        """Detect if window is likely open based on rapid temperature drop.

        This is the polling fallback - real-time detection is preferred.
        Uses same thresholds as real-time detection for consistency.
        """
        if self._last_indoor_temp is None or self._last_update is None:
            return False

        time_delta = now - self._last_update
        if time_delta <= 0:
            return False

        # Calculate temperature change rate (°C per minute)
        temp_change = current_temp - self._last_indoor_temp
        rate_per_minute = (temp_change / time_delta) * 60

        # Thresholds aligned with real-time detection:
        # - 0.7°C/min while heating
        # - 1.2°C/min regardless
        # Note: This is polling fallback, real-time detection with consecutive
        # readings is more accurate and less prone to false positives
        if self._last_heating_state and rate_per_minute < -0.7:
            return True
        if rate_per_minute < -1.2:
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
