"""DataUpdateCoordinator for Home Performance."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONF_EFFICIENCY_FACTOR,
    CONF_ENABLE_DYNAMIC_COP,
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
    DEFAULT_EFFICIENCY_FACTORS,
    DEFAULT_ENABLE_DYNAMIC_COP,
    DEFAULT_HEAT_SOURCE_TYPE,
    DEFAULT_NOTIFICATION_DELAY,
    DEFAULT_POWER_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HEAT_SOURCE_HEATPUMP,
    HEAT_SOURCE_MIGRATION,
    HEAT_SOURCES_REQUIRING_ENERGY,
    MIN_DELTA_T,
    MIN_HEATING_TIME_HOURS,
)
from .models import ThermalDataPoint, ThermalLossModel

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

        # Heat source type - migrate legacy types if needed
        raw_heat_source = config.get(CONF_HEAT_SOURCE_TYPE, DEFAULT_HEAT_SOURCE_TYPE)
        self.heat_source_type: str = HEAT_SOURCE_MIGRATION.get(raw_heat_source, raw_heat_source)
        if raw_heat_source != self.heat_source_type:
            _LOGGER.info(
                "[%s] Migrated heat source type: %s → %s", self.zone_name, raw_heat_source, self.heat_source_type
            )

        self.heater_power: float | None = config.get(CONF_HEATER_POWER)
        self.surface: float | None = config.get(CONF_SURFACE)
        self.volume: float | None = config.get(CONF_VOLUME)
        self.power_sensor: str | None = config.get(CONF_POWER_SENSOR)
        self.energy_sensor: str | None = config.get(CONF_ENERGY_SENSOR)
        self.power_threshold: float = config.get(CONF_POWER_THRESHOLD) or DEFAULT_POWER_THRESHOLD
        self.window_sensor: str | None = config.get(CONF_WINDOW_SENSOR)

        # Weather settings
        self.weather_entity: str | None = config.get(CONF_WEATHER_ENTITY)
        # Normalize orientation to lowercase (supports legacy uppercase values)
        raw_orientation = config.get(CONF_ROOM_ORIENTATION)
        self.room_orientation: str | None = raw_orientation.lower() if raw_orientation else None

        # Notification settings
        self.window_notification_enabled: bool = config.get(CONF_WINDOW_NOTIFICATION_ENABLED, False)
        self.notify_device: str | None = config.get(CONF_NOTIFY_DEVICE)
        self.notification_delay: int = config.get(CONF_NOTIFICATION_DELAY, DEFAULT_NOTIFICATION_DELAY)

        # Efficiency factor - use configured value or default based on heat source type
        self.efficiency_factor: float = config.get(
            CONF_EFFICIENCY_FACTOR, DEFAULT_EFFICIENCY_FACTORS.get(self.heat_source_type, 1.0)
        )

        # Dynamic COP calculation (only for heat pumps)
        self.enable_dynamic_cop: bool = (
            self.heat_source_type == HEAT_SOURCE_HEATPUMP
            and config.get(CONF_ENABLE_DYNAMIC_COP, DEFAULT_ENABLE_DYNAMIC_COP)
            and self.energy_sensor is not None
        )

        # For energy-based sources, energy_sensor should be used for K calculation
        self._uses_energy_based_calculation = (
            self.heat_source_type in HEAT_SOURCES_REQUIRING_ENERGY and self.energy_sensor is not None
        )

        _LOGGER.info(
            "HomePerformance coordinator initialized for zone '%s': "
            "heat_source=%s, efficiency_factor=%.2f, indoor_temp=%s, outdoor_temp=%s, heating_entity=%s, "
            "power_sensor=%s, energy_sensor=%s, heater_power=%s, window_sensor=%s",
            self.zone_name,
            self.heat_source_type,
            self.efficiency_factor,
            self.indoor_temp_sensor,
            self.outdoor_temp_sensor,
            self.heating_entity,
            self.power_sensor,
            self.energy_sensor,
            f"{self.heater_power}W" if self.heater_power else "N/A (energy-based)",
            self.window_sensor,
        )

        # Thermal model
        self.thermal_model = ThermalLossModel(
            zone_name=self.zone_name,
            heater_power=self.heater_power,
            surface=self.surface,
            volume=self.volume,
            efficiency_factor=self.efficiency_factor,
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
        self._last_external_energy: float | None = None  # For energy-based sources

        # Energy sensor tracking (external daily energy counter)
        # User provides a daily counter (e.g., Utility Meter) - we use its value directly
        self._energy_sensor_daily_kwh: float = 0.0  # Value from external energy sensor

        # Daily counters (reset at midnight) - for minuit-minuit consistency
        self._last_daily_reset_date: str | None = None
        self._daily_reset_datetime: Any = None  # datetime for utility meter compatibility
        self._estimated_energy_daily_kwh: float = 0.0  # Estimated energy since midnight
        self._heating_seconds_daily: float = 0.0  # Heating time since midnight
        self._delta_t_sum_daily: float = 0.0  # Sum of ΔT for daily average
        self._delta_t_count_daily: int = 0  # Count of samples for daily average
        self._indoor_temp_min_daily: float | None = None  # Min indoor temp since midnight
        self._indoor_temp_max_daily: float | None = None  # Max indoor temp since midnight

        # Daily wind tracking (for history archival)
        self._wind_speed_sum_daily: float = 0.0  # Sum of wind speed for daily average
        self._wind_speed_count_daily: int = 0  # Count of wind samples
        self._wind_direction_counts_daily: dict[str, int] = {}  # Count per direction

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

        # Notification tracking
        self._notification_task: asyncio.Task | None = None  # Delayed notification task
        self._last_notification_time: float | None = None  # Cooldown tracking

        # Persistence - use slugify for consistent handling of special characters
        zone_slug = slugify(self.zone_name, separator="_")
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{zone_slug}",
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
                old_power = (
                    float(old_state.state)
                    if old_state and old_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
                    else 0.0
                )
            except (ValueError, TypeError):
                old_power = 0.0

            now = time.time()
            is_heating_now = new_power > self.power_threshold
            was_heating = old_power > self.power_threshold

            _LOGGER.debug(
                "[%s] Power sensor changed: %.1fW -> %.1fW (heating: %s -> %s)",
                self.zone_name,
                old_power,
                new_power,
                was_heating,
                is_heating_now,
            )

            # Heating started
            if is_heating_now and not self._is_heating_realtime:
                self._heating_start_time = now
                self._is_heating_realtime = True
                _LOGGER.info("[%s] 🔥 Heating started (real-time detection)", self.zone_name)
                # Trigger notification if window is already open
                if self._window_open_realtime:
                    self._schedule_window_notification()

            # Heating stopped
            elif not is_heating_now and self._is_heating_realtime:
                if self._heating_start_time is not None:
                    duration = now - self._heating_start_time
                    self._heating_seconds_daily += duration
                    # Update estimated energy (only if heater_power is available)
                    if self.heater_power is not None and self.heater_power > 0:
                        energy_kwh = (self.heater_power / 1000) * (duration / 3600)
                        self._estimated_energy_daily_kwh += energy_kwh
                        _LOGGER.info(
                            "[%s] ❄️ Heating stopped (real-time). Duration: %.1fs (%.2f min), Energy: %.4f kWh",
                            self.zone_name,
                            duration,
                            duration / 60,
                            energy_kwh,
                        )
                    else:
                        _LOGGER.info(
                            "[%s] ❄️ Heating stopped (real-time). Duration: %.1fs (%.2f min)",
                            self.zone_name,
                            duration,
                            duration / 60,
                        )
                self._heating_start_time = None
                self._is_heating_realtime = False
                # Cancel any pending window notification
                self._cancel_window_notification()

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
                        new_temp, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
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
                        self._is_heating_realtime and rate_per_minute < DROP_THRESHOLD_HEATING
                    ) or rate_per_minute < DROP_THRESHOLD_ANY

                    if is_rapid_drop:
                        self._consecutive_drops += 1
                        if self._consecutive_drops >= CONSECUTIVE_DROPS_REQUIRED:
                            if not was_window_open:
                                self._window_open_realtime = True
                                self._window_open_since = now
                                _LOGGER.warning(
                                    "[%s] 🪟 Window OPEN detected! Temp drop: %.2f°C/min (heating: %s)",
                                    self.zone_name,
                                    abs(rate_per_minute),
                                    self._is_heating_realtime,
                                )
                                # Trigger notification if heating is on and notifications enabled
                                if self._is_heating_realtime:
                                    self._schedule_window_notification()
                    elif rate_per_minute > 0.1:
                        # Temperature rising = window likely closed
                        self._consecutive_drops = 0
                        if was_window_open:
                            _LOGGER.info("[%s] 🪟 Window CLOSED (temperature rising)", self.zone_name)
                            self._cancel_window_notification()
                        self._window_open_realtime = False
                        self._window_open_since = None
                    elif abs(rate_per_minute) < 0.2:
                        # Temperature stable (not dropping fast) - close window after 5 min
                        self._consecutive_drops = 0
                        if was_window_open and self._window_open_since:
                            minutes_open = (now - self._window_open_since) / 60
                            if minutes_open > 5:
                                _LOGGER.info(
                                    "[%s] 🪟 Window CLOSED (temperature stabilized after %.1f min)",
                                    self.zone_name,
                                    minutes_open,
                                )
                                self._cancel_window_notification()
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

    def _schedule_window_notification(self) -> None:
        """Schedule a window open notification after the configured delay."""
        if not self.window_notification_enabled or not self.notify_device:
            return

        # Cancel any existing notification task
        if self._notification_task and not self._notification_task.done():
            self._notification_task.cancel()

        # Create a new notification task
        self._notification_task = self.hass.async_create_task(self._async_send_window_notification())

    def _cancel_window_notification(self) -> None:
        """Cancel any pending window notification."""
        if self._notification_task and not self._notification_task.done():
            self._notification_task.cancel()
            self._notification_task = None
            _LOGGER.debug("[%s] Window notification cancelled", self.zone_name)

    async def _async_send_window_notification(self) -> None:
        """Send window open notification after delay."""
        try:
            # Wait for the configured delay
            await asyncio.sleep(self.notification_delay * 60)

            # Re-check conditions after delay
            if not self._window_open_realtime or not self._is_heating_realtime:
                _LOGGER.debug("[%s] Conditions no longer met, skipping notification", self.zone_name)
                return

            # Cooldown: don't send notifications more than once per 15 minutes
            now = time.time()
            if self._last_notification_time and (now - self._last_notification_time) < 900:
                _LOGGER.debug("[%s] Notification cooldown active, skipping", self.zone_name)
                return

            # Get notify service name from device
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get(self.notify_device)

            if not device:
                _LOGGER.warning("[%s] Notify device not found: %s", self.zone_name, self.notify_device)
                return

            # Find the mobile_app notify service for this device
            # The service name is typically notify.mobile_app_<device_name>
            notify_service = None
            for identifier in device.identifiers:
                if identifier[0] == "mobile_app":
                    # The device ID format is usually the device name
                    device_name = identifier[1].lower().replace(" ", "_").replace("-", "_")
                    notify_service = f"mobile_app_{device_name}"
                    break

            if not notify_service:
                # Fallback: try using device name directly
                if device.name:
                    device_name = device.name.lower().replace(" ", "_").replace("-", "_")
                    notify_service = f"mobile_app_{device_name}"
                else:
                    _LOGGER.warning("[%s] Could not determine notify service for device", self.zone_name)
                    return

            # Get translated message based on HA language
            lang = self.hass.config.language or "en"
            title = f"⚠️ {self.zone_name}"
            if lang.startswith("fr"):
                message = "Fenêtre ouverte · Chauffage actif"
            elif lang.startswith("it"):
                message = "Finestra aperta · Riscaldamento attivo"
            else:  # English default
                message = "Window open · Heating active"

            # Send the notification
            await self.hass.services.async_call(
                "notify",
                notify_service,
                {
                    "title": title,
                    "message": message,
                    "data": {
                        "tag": f"home_performance_window_{self.zone_name}",
                        "group": "home_performance",
                    },
                },
                blocking=False,
            )

            self._last_notification_time = now
            _LOGGER.info("[%s] 📱 Window open notification sent", self.zone_name)

        except asyncio.CancelledError:
            _LOGGER.debug("[%s] Window notification task cancelled", self.zone_name)
        except Exception as err:
            _LOGGER.error("[%s] Failed to send window notification: %s", self.zone_name, err)

    async def async_shutdown(self) -> None:
        """Clean up when coordinator is shut down."""
        # Cancel any pending notification
        self._cancel_window_notification()

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
            if self.heater_power is not None and self.heater_power > 0:
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

                # Note: energy_sensor_daily_kwh is NOT restored from storage
                # It's read directly from the external energy sensor on each update

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
                # Note: energy_sensor_daily_kwh is read directly from sensor, not stored
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
                _LOGGER.debug("[%s] Temperature sensors not available yet, returning restored data", self.zone_name)
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

            # For energy-based sources, get energy increment to pass to model
            measured_energy_increment = None
            if self._uses_energy_based_calculation and heating_on:
                # Get energy from external sensor and calculate increment
                external_energy = self._get_external_energy()
                if external_energy is not None and hasattr(self, "_last_external_energy"):
                    if self._last_external_energy is not None:
                        measured_energy_increment = max(0, external_energy - self._last_external_energy)
                    self._last_external_energy = external_energy
                elif external_energy is not None:
                    self._last_external_energy = external_energy

            self.thermal_model.add_data_point(data_point, measured_energy_increment)

            # Detect window open (real sensor if configured, else temperature-based detection)
            window_open, window_detection_method = self._get_window_open_state(indoor_temp, now)

            # Update daily counters (minuit-minuit)
            delta_t = indoor_temp - outdoor_temp
            self._update_daily_counters(now, heating_on, delta_t, indoor_temp)

            # Update tracking values
            self._last_indoor_temp = indoor_temp
            self._last_heating_state = heating_on
            self._last_update = now

            # Get analysis from model (for K coefficient - rolling 24h)
            analysis = self.thermal_model.get_analysis()

            # Update measured energy from power sensor (if configured)
            measured_power = self._update_measured_energy(now)

            # Get external energy sensor value (if configured)
            # If user configured an energy_sensor, we use its value DIRECTLY
            # (user is responsible for providing a daily counter like Utility Meter)
            external_energy = self._get_external_energy()
            if external_energy is not None:
                self._energy_sensor_daily_kwh = external_energy

            # Get weather data (wind)
            weather_data = self._get_weather_data()

            # Update wind counters for daily average
            self._update_wind_counters(weather_data)

            # Calculate daily values (minuit-minuit)
            # Include ongoing heating session in the total
            heating_seconds = self._heating_seconds_daily
            estimated_energy = self._estimated_energy_daily_kwh
            if self._is_heating_realtime and self._heating_start_time is not None:
                # Add time from current ongoing heating session
                ongoing_duration = now - self._heating_start_time
                heating_seconds += ongoing_duration
                # Add energy from current ongoing heating session
                if self.heater_power is not None and self.heater_power > 0:
                    ongoing_energy_kwh = (self.heater_power / 1000) * (ongoing_duration / 3600)
                    estimated_energy += ongoing_energy_kwh
            heating_hours_daily = heating_seconds / 3600

            # ΔT moyen : utiliser la valeur 24h glissante du modèle thermique
            # (plus stable que le calcul depuis minuit)
            avg_delta_t_rolling = analysis.get("avg_delta_t") or delta_t

            # Calculate dynamic COP for heat pumps (if enabled)
            measured_cop = None
            cop_status = None
            if self.enable_dynamic_cop:
                measured_cop, cop_status = self._calculate_dynamic_cop(
                    k_coefficient=analysis.get("k_coefficient"),
                    avg_delta_t=avg_delta_t_rolling,
                    heating_hours=heating_hours_daily,
                    energy_consumed=self._energy_sensor_daily_kwh,
                    data_ready=analysis.get("data_ready", False),
                )

            # Periodically save data to persistent storage
            await self._async_maybe_save()

            return {
                # Current values
                "indoor_temp": indoor_temp,
                "outdoor_temp": outdoor_temp,
                "heating_on": heating_on,
                "delta_t": delta_t,
                "window_open": window_open,
                "window_detection_method": window_detection_method,
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
                "daily_energy_kwh": estimated_energy,
                # Cumulative energy (for Energy Dashboard)
                "total_energy_kwh": analysis.get("total_energy_kwh"),
                # Measured energy (from power sensor)
                "measured_power_w": measured_power,
                "measured_energy_daily_kwh": self._measured_energy_daily_kwh,
                "measured_energy_total_kwh": self._measured_energy_total_kwh,
                "daily_reset_datetime": self._daily_reset_datetime,
                "power_sensor_configured": self.power_sensor is not None,
                # External energy sensor (if configured, takes priority for K calculation)
                "external_energy_total_kwh": external_energy,
                "external_energy_daily_kwh": self._energy_sensor_daily_kwh if self.energy_sensor else None,
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
                "effective_power": analysis.get("effective_power"),
                "derived_power": analysis.get("derived_power"),
                "heat_source_type": self.heat_source_type,
                "efficiency_factor": self.efficiency_factor,
                "enable_dynamic_cop": self.enable_dynamic_cop,
                "measured_cop": measured_cop,
                "cop_status": cop_status,
                "surface": self.surface,
                "volume": self.volume,
                "power_threshold": self.power_threshold,
                # Insulation rating (with season/inference support)
                "insulation_rating": self.thermal_model.get_insulation_rating(),
                "insulation_status": self.thermal_model.get_insulation_status(),
                "last_valid_k": self.thermal_model.last_valid_k,
                # Weather data (wind)
                "wind_speed": weather_data.get("wind_speed"),
                "wind_speed_unit": weather_data.get("wind_speed_unit"),
                "wind_bearing": weather_data.get("wind_bearing"),
                "wind_direction": weather_data.get("wind_direction"),
                "wind_exposure": weather_data.get("wind_exposure"),
                "room_orientation": weather_data.get("room_orientation"),
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
            "window_detection_method": "sensor" if self.window_sensor else "temperature",
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
            "external_energy_total_kwh": None,
            "external_energy_daily_kwh": None,
            "energy_sensor_configured": self.energy_sensor is not None,
            "data_hours": 0,
            "samples_count": 0,
            "data_ready": False,
            "storage_loaded": self._data_loaded,
            "history_days": 0,
            "history_has_valid_k": False,
            "heater_power": self.heater_power,
            "effective_power": self.heater_power,
            "derived_power": None,
            "heat_source_type": self.heat_source_type,
            "efficiency_factor": self.efficiency_factor,
            "enable_dynamic_cop": self.enable_dynamic_cop,
            "measured_cop": None,
            "cop_status": "waiting_data" if self.enable_dynamic_cop else None,
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
            # Weather data
            "wind_speed": None,
            "wind_speed_unit": None,
            "wind_bearing": None,
            "wind_direction": None,
            "wind_exposure": None,
            "room_orientation": self.room_orientation,
        }

    def _get_restored_data(self) -> dict[str, Any]:
        """Return data from restored thermal model (when sensors not yet available)."""
        analysis = self.thermal_model.get_analysis()

        # Calculate restored heating values
        # Include ongoing heating session in the total
        heating_seconds = self._heating_seconds_daily
        estimated_energy = self._estimated_energy_daily_kwh
        if self._is_heating_realtime and self._heating_start_time is not None:
            ongoing_duration = time.time() - self._heating_start_time
            heating_seconds += ongoing_duration
            # Add energy from current ongoing heating session
            if self.heater_power is not None and self.heater_power > 0:
                ongoing_energy_kwh = (self.heater_power / 1000) * (ongoing_duration / 3600)
                estimated_energy += ongoing_energy_kwh
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
            "daily_energy_kwh": estimated_energy,
            "total_energy_kwh": analysis.get("total_energy_kwh"),
            # Measured energy
            "measured_power_w": None,
            "measured_energy_daily_kwh": self._measured_energy_daily_kwh,
            "measured_energy_total_kwh": self._measured_energy_total_kwh,
            "daily_reset_datetime": self._daily_reset_datetime,
            "power_sensor_configured": self.power_sensor is not None,
            "external_energy_total_kwh": None,
            "external_energy_daily_kwh": self._energy_sensor_daily_kwh if self.energy_sensor else None,
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
            "effective_power": analysis.get("effective_power"),
            "derived_power": analysis.get("derived_power"),
            "heat_source_type": self.heat_source_type,
            "efficiency_factor": self.efficiency_factor,
            "enable_dynamic_cop": self.enable_dynamic_cop,
            "measured_cop": None,
            "cop_status": "waiting_data" if self.enable_dynamic_cop else None,
            "surface": self.surface,
            "volume": self.volume,
            "power_threshold": self.power_threshold,
            # Restored insulation rating (with season/inference support)
            "insulation_rating": self.thermal_model.get_insulation_rating(),
            "insulation_status": self.thermal_model.get_insulation_status(),
            "last_valid_k": self.thermal_model.last_valid_k,
            # Weather data (get current)
            **self._get_weather_data(),
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
                self.zone_name,
                self._last_daily_reset_date,
                today,
                self._delta_t_count_daily,
            )

            # Archive yesterday's data BEFORE resetting (if we have data)
            if self._last_daily_reset_date and self._delta_t_count_daily > 0:
                _LOGGER.warning(
                    "[%s] 📦 ARCHIVING day %s with %d samples",
                    self.zone_name,
                    self._last_daily_reset_date,
                    self._delta_t_count_daily,
                )
                self._archive_daily_data(self._last_daily_reset_date)
            else:
                _LOGGER.warning(
                    "[%s] ⚠️ SKIPPING archive - last_date=%s, samples=%d",
                    self.zone_name,
                    self._last_daily_reset_date,
                    self._delta_t_count_daily,
                )

            _LOGGER.info("[%s] 🌙 Daily reset (new day: %s)", self.zone_name, today)
            # Reset all daily counters
            self._measured_energy_daily_kwh = 0.0
            self._estimated_energy_daily_kwh = 0.0
            self._heating_seconds_daily = 0.0
            self._delta_t_sum_daily = 0.0
            self._delta_t_count_daily = 0
            self._indoor_temp_min_daily = None
            self._indoor_temp_max_daily = None
            self._reset_daily_wind_counters()
            self._last_daily_reset_date = today
            self._daily_reset_datetime = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)

            # Note: energy_sensor_daily_kwh is read directly from external sensor
            # No need to reset it here - the external Utility Meter handles its own reset

    def _archive_daily_data(self, date: str) -> None:
        """Archive a day's data to the thermal model's 7-day history.

        Called at midnight before resetting daily counters.

        Args:
            date: The date (YYYY-MM-DD) of the data to archive

        Energy source priority (most accurate first):
        1. energy_sensor (external energy meter - direct measurement)
        2. measured_energy (integrated from power_sensor - calculated)
        3. estimated_energy (heater_power × time - estimation)
        """
        # Calculate averages
        avg_delta_t = self._delta_t_sum_daily / self._delta_t_count_daily if self._delta_t_count_daily > 0 else 0.0

        # Get average temps from the last aggregation or estimate
        avg_indoor = 0.0
        avg_outdoor = 0.0

        # Try to get from model's last aggregation
        if hasattr(self.thermal_model, "_last_aggregation") and self.thermal_model._last_aggregation:
            agg = self.thermal_model._last_aggregation
            avg_indoor = agg.avg_indoor_temp
            avg_outdoor = agg.avg_outdoor_temp

        heating_hours = self._heating_seconds_daily / 3600

        # Determine the best energy source for K calculation
        # Priority: energy_sensor > measured_energy (power_sensor) > estimated_energy
        energy_kwh = 0.0
        energy_source = "none"

        # 1. Check for external energy sensor (most accurate - actual metered consumption)
        if self.energy_sensor is not None and self._energy_sensor_daily_kwh > 0:
            energy_kwh = self._energy_sensor_daily_kwh
            energy_source = "energy_sensor"
        # 2. Check for measured energy from power sensor integration (accurate)
        elif self._measured_energy_daily_kwh > 0:
            energy_kwh = self._measured_energy_daily_kwh
            energy_source = "power_sensor"
        # 3. Fall back to estimated energy from heater_power (least accurate)
        elif self._estimated_energy_daily_kwh > 0:
            energy_kwh = self._estimated_energy_daily_kwh
            energy_source = "heater_power"

        # Get current K_7j BEFORE adding today's data (this is the score we had today)
        current_k_7d = self.thermal_model.k_coefficient_7d

        # Calculate temperature variation (for stability check in K_7d calculation)
        temp_variation = None
        if self._indoor_temp_min_daily is not None and self._indoor_temp_max_daily is not None:
            temp_variation = self._indoor_temp_max_daily - self._indoor_temp_min_daily

        # Get wind averages for the day
        avg_wind_speed, dominant_wind_direction = self._get_daily_wind_averages()

        _LOGGER.info(
            "[%s] 📦 Archiving daily data for %s: heating=%.1fh, ΔT=%.1f°C, "
            "energy=%.2f kWh [%s], samples=%d, temp_var=%.1f°C, k_7d=%.1f, wind=%.1f km/h %s",
            self.zone_name,
            date,
            heating_hours,
            avg_delta_t,
            energy_kwh,
            energy_source,
            self._delta_t_count_daily,
            temp_variation if temp_variation else 0.0,
            current_k_7d if current_k_7d else 0.0,
            avg_wind_speed if avg_wind_speed else 0.0,
            dominant_wind_direction if dominant_wind_direction else "N/A",
        )

        # Add to thermal model history (with the K_7j score we had at this moment)
        self.thermal_model.add_daily_summary(
            date=date,
            heating_hours=heating_hours,
            avg_delta_t=avg_delta_t,
            energy_kwh=energy_kwh,
            avg_indoor_temp=avg_indoor,
            avg_outdoor_temp=avg_outdoor,
            sample_count=self._delta_t_count_daily,
            k_7d=current_k_7d,
            temp_variation=temp_variation,
            avg_wind_speed=avg_wind_speed,
            dominant_wind_direction=dominant_wind_direction,
        )

        # Log history status after archiving
        history_count = len(self.thermal_model.daily_history)
        new_k_7d = self.thermal_model.k_coefficient_7d
        _LOGGER.warning(
            "[%s] ✅ ARCHIVE COMPLETE - history_days=%d, k_7d=%s W/°C (energy_source=%s)",
            self.zone_name,
            history_count,
            f"{new_k_7d:.1f}" if new_k_7d else "None",
            energy_source,
        )

    def reset_history(self) -> None:
        """Reset the 7-day history (manual reset service).

        Use this after insulation work or to clear anomalous data.
        """
        _LOGGER.info("[%s] 🔄 Manual history reset requested", self.zone_name)
        self.thermal_model.clear_history()

    def reset_all_data(self) -> None:
        """Reset ALL calibration data for complete fresh start.

        Use this when measurements were taken during unusual conditions,
        or when user wants to completely recalibrate from scratch.
        """
        _LOGGER.info("[%s] 🗑️ Complete data reset requested", self.zone_name)

        # Reset thermal model (history, data points, K coefficients)
        self.thermal_model.clear_all()

        # Reset coordinator's daily counters
        self._heating_seconds_daily = 0.0
        self._delta_t_sum_daily = 0.0
        self._delta_t_count_daily = 0
        self._estimated_energy_daily_kwh = 0.0
        self._indoor_temp_min_daily = None
        self._indoor_temp_max_daily = None
        self._reset_daily_wind_counters()

        # Reset measured energy counters
        self._measured_energy_daily_kwh = 0.0
        self._measured_energy_total_kwh = 0.0
        self._last_power_value = None
        self._last_power_update = None

        # Reset real-time tracking
        self._last_indoor_temp = None
        self._last_heating_state = None
        self._last_update = None

        # Reset window detection
        self._window_open_realtime = False
        self._window_open_since = None
        self._consecutive_drops = 0
        self._last_temp_value = None
        self._last_temp_time = None

        _LOGGER.info("[%s] ✅ Complete reset finished - zone ready for fresh calibration", self.zone_name)

    def _update_daily_counters(self, now: float, heating_on: bool, delta_t: float, indoor_temp: float) -> None:
        """Update daily counters (minuit-minuit)."""
        if self._last_update is not None:
            time_delta_seconds = now - self._last_update
            time_delta_hours = time_delta_seconds / 3600

            # Update heating time and energy ONLY if no power_sensor (no real-time listener)
            # When power_sensor is configured, the real-time listener handles this more precisely
            if not self.power_sensor:
                if self._last_heating_state:
                    self._heating_seconds_daily += time_delta_seconds
                    # Update estimated energy (power * time) - only if heater_power is available
                    if self.heater_power is not None and self.heater_power > 0:
                        energy_kwh = (self.heater_power / 1000) * time_delta_hours
                        self._estimated_energy_daily_kwh += energy_kwh

        # Update ΔT average (always done via polling)
        self._delta_t_sum_daily += delta_t
        self._delta_t_count_daily += 1

        # Track indoor temperature min/max for stability calculation
        if self._indoor_temp_min_daily is None or indoor_temp < self._indoor_temp_min_daily:
            self._indoor_temp_min_daily = indoor_temp
        if self._indoor_temp_max_daily is None or indoor_temp > self._indoor_temp_max_daily:
            self._indoor_temp_max_daily = indoor_temp

    def _update_wind_counters(self, weather_data: dict[str, Any]) -> None:
        """Update daily wind counters for history archival."""
        wind_speed = weather_data.get("wind_speed")
        wind_direction = weather_data.get("wind_direction")

        if wind_speed is not None:
            self._wind_speed_sum_daily += wind_speed
            self._wind_speed_count_daily += 1

        if wind_direction is not None:
            self._wind_direction_counts_daily[wind_direction] = (
                self._wind_direction_counts_daily.get(wind_direction, 0) + 1
            )

    def _get_daily_wind_averages(self) -> tuple[float | None, str | None]:
        """Calculate average wind speed and dominant direction for the day."""
        # Average wind speed
        avg_wind_speed = None
        if self._wind_speed_count_daily > 0:
            avg_wind_speed = self._wind_speed_sum_daily / self._wind_speed_count_daily

        # Dominant wind direction (most frequent)
        dominant_direction = None
        if self._wind_direction_counts_daily:
            dominant_direction = max(self._wind_direction_counts_daily, key=self._wind_direction_counts_daily.get)

        return avg_wind_speed, dominant_direction

    def _reset_daily_wind_counters(self) -> None:
        """Reset wind counters at midnight."""
        self._wind_speed_sum_daily = 0.0
        self._wind_speed_count_daily = 0
        self._wind_direction_counts_daily = {}

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
                    temp_value, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
                )

            return temp_value
        except (ValueError, TypeError):
            return None

    def _calculate_dynamic_cop(
        self,
        k_coefficient: float | None,
        avg_delta_t: float | None,
        heating_hours: float,
        energy_consumed: float,
        data_ready: bool,
    ) -> tuple[float | None, str]:
        """Calculate dynamic COP for heat pumps.

        Formula: COP = Thermal_energy / Electrical_energy
        Where: Thermal_energy = K × ΔT × hours (in Wh, then converted to kWh)

        Returns:
            Tuple of (measured_cop, status_message)
        """
        # Check prerequisites
        if not data_ready or k_coefficient is None:
            return None, "waiting_calibration"

        if avg_delta_t is None or avg_delta_t < MIN_DELTA_T:
            return None, "insufficient_delta_t"

        if heating_hours < MIN_HEATING_TIME_HOURS:
            return None, "insufficient_heating_time"

        if energy_consumed <= 0:
            return None, "no_energy_data"

        # Calculate thermal energy needed (in kWh)
        # K is in W/°C, so K × ΔT × hours = Wh, divide by 1000 for kWh
        thermal_energy_kwh = (k_coefficient * avg_delta_t * heating_hours) / 1000

        # COP = Thermal output / Electrical input
        cop = thermal_energy_kwh / energy_consumed

        # Sanity check: COP should be between 1.0 and 7.0 for heat pumps
        if cop < 1.0:
            _LOGGER.warning(
                "[%s] Calculated COP %.2f is below 1.0 - check sensor configuration",
                self.zone_name,
                cop,
            )
            return cop, "low_cop_warning"

        if cop > 7.0:
            _LOGGER.warning(
                "[%s] Calculated COP %.2f is unusually high - check sensor configuration",
                self.zone_name,
                cop,
            )
            return cop, "high_cop_warning"

        return cop, "ok"

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

    def _get_weather_data(self) -> dict[str, Any]:
        """Get weather data (wind speed, bearing, direction) from weather entity."""
        result = {
            "wind_speed": None,
            "wind_speed_unit": None,
            "wind_bearing": None,
            "wind_direction": None,
            "wind_exposure": None,
            "room_orientation": self.room_orientation,
        }

        if self.weather_entity is None:
            return result

        state = self.hass.states.get(self.weather_entity)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return result

        attrs = state.attributes

        # Get wind speed
        wind_speed = attrs.get("wind_speed")
        if wind_speed is not None:
            try:
                result["wind_speed"] = float(wind_speed)
                result["wind_speed_unit"] = attrs.get("wind_speed_unit", "km/h")
            except (ValueError, TypeError):
                pass

        # Get wind bearing and convert to direction
        wind_bearing = attrs.get("wind_bearing")
        if wind_bearing is not None:
            try:
                bearing = int(wind_bearing)
                result["wind_bearing"] = bearing
                # Convert bearing to direction (N, NE, E, SE, S, SW, W, NW)
                directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
                index = int(((bearing + 22.5) % 360) / 45)
                result["wind_direction"] = directions[index]
            except (ValueError, TypeError):
                pass

        # Calculate wind exposure if room orientation is configured
        if self.room_orientation and result["wind_direction"]:
            result["wind_exposure"] = self._calculate_wind_exposure(result["wind_direction"], self.room_orientation)

        return result

    def _calculate_wind_exposure(self, wind_direction: str, room_orientation: str) -> str:
        """Calculate if room is exposed or sheltered based on wind direction.

        Simplified logic (works for detached and semi-detached houses):
            - "exposed": Wind within ±45° of facade direction
            - "sheltered": Wind outside ±45° of facade direction
        """
        # Direction order for calculation (lowercase)
        directions = ["n", "ne", "e", "se", "s", "sw", "w", "nw"]

        # Normalize inputs to lowercase for comparison
        wind_dir_lower = wind_direction.lower() if wind_direction else ""
        room_orient_lower = room_orientation.lower() if room_orientation else ""

        try:
            wind_idx = directions.index(wind_dir_lower)
            room_idx = directions.index(room_orient_lower)
        except ValueError:
            return "unknown"

        # Calculate angular difference (0-4 steps, where 4 is opposite)
        diff = abs(wind_idx - room_idx)
        if diff > 4:
            diff = 8 - diff

        # Simplified: exposed only if wind is within ±45° (diff <= 1)
        if diff <= 1:
            return "exposed"  # Wind facing facade (±45°)
        else:
            return "sheltered"  # Wind from side or back

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
                        self.zone_name,
                        self.power_sensor,
                        power_w,
                        self.power_threshold,
                        is_heating,
                    )
                    return is_heating
                except (ValueError, TypeError) as err:
                    _LOGGER.warning("[%s] Could not parse power sensor value: %s", self.zone_name, err)

            # Power sensor configured but unavailable -> assume not heating
            # DO NOT fallback to switch (it's always ON for thermostatic radiators)
            _LOGGER.debug(
                "[%s] Power sensor %s unavailable (state=%s), assuming not heating",
                self.zone_name,
                self.power_sensor,
                power_state.state if power_state else "None",
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
                self.zone_name,
                self.heating_entity,
                hvac_mode,
                hvac_action,
            )
            # Check hvac_action first (most reliable - indicates actual heating activity)
            if hvac_action:
                return hvac_action in ("heating", "heat")
            # Fallback to hvac_mode (less reliable - only indicates mode, not activity)
            return hvac_mode in ("heat", "heat_cool") and hvac_mode not in ("off", STATE_UNAVAILABLE, STATE_UNKNOWN)

        # Handle switch/input_boolean
        is_on = state.state == STATE_ON
        _LOGGER.debug(
            "[%s] Heating via switch %s: state=%s -> heating=%s",
            self.zone_name,
            self.heating_entity,
            state.state,
            is_on,
        )
        return is_on

    def _get_window_open_state(self, current_temp: float, now: float) -> tuple[bool, str]:
        """Get window open state and detection method.

        Returns:
            Tuple of (is_window_open: bool, detection_method: str)

        Detection method:
        - "sensor": Using configured binary_sensor (window/door contact sensor)
        - "temperature": Using temperature-based detection (real-time + polling fallback)
        """
        # Priority 1: Use real window/door sensor if configured
        if self.window_sensor:
            state = self.hass.states.get(self.window_sensor)
            if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                is_open = state.state == STATE_ON
                return (is_open, "sensor")
            # Sensor unavailable - fall back to temperature detection
            _LOGGER.debug(
                "[%s] Window sensor %s unavailable, using temperature detection", self.zone_name, self.window_sensor
            )

        # Priority 2: Temperature-based detection (real-time + polling fallback)
        is_open = self._window_open_realtime or self._detect_window_open(current_temp, now)
        return (is_open, "temperature")

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
            self._daily_reset_datetime = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)

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
