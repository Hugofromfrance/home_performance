"""Sensor platform for Home Performance."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, MIN_DATA_HOURS, SENSOR_ENTITY_SUFFIXES, VERSION
from .coordinator import HomePerformanceCoordinator

_LOGGER = logging.getLogger(__name__)


def format_duration(hours: float | None) -> str | None:
    """Convert decimal hours to human readable format (Xh Ymin)."""
    if hours is None:
        return None
    total_minutes = int(round(hours * 60))
    h = total_minutes // 60
    m = total_minutes % 60
    if h == 0:
        return f"{m}min"
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}min"


def get_energy_performance(
    daily_kwh: float | None,
    heater_power_w: float | None,
    derived_power_w: float | None = None,
) -> dict[str, Any]:
    """
    Evaluate energy performance based on French national statistics.

    Thresholds based on heater power (or derived power for energy-based sources):
    - Excellent: < (power/1000) * 4 kWh/day (-40% vs national average)
    - Standard: between excellent and (power/1000) * 6 kWh/day
    - To optimize: > (power/1000) * 6 kWh/day

    Args:
        daily_kwh: Daily energy consumption in kWh
        heater_power_w: Declared heater power in Watts (may be None for energy-based sources)
        derived_power_w: Calculated average power from energy/time (fallback for energy-based sources)
    """
    # Use heater_power if available, otherwise use derived_power
    effective_power = heater_power_w if heater_power_w and heater_power_w > 0 else derived_power_w

    if daily_kwh is None or effective_power is None or effective_power <= 0:
        return {
            "level": None,
            "icon": "mdi:help-circle",
            "message": "Waiting for data",
            "saving_percent": None,
            "excellent_threshold": None,
            "standard_threshold": None,
        }

    # Thresholds based on effective power
    excellent_threshold = (effective_power / 1000) * 4
    standard_threshold = (effective_power / 1000) * 6

    if daily_kwh < excellent_threshold:
        saving = round((1 - daily_kwh / standard_threshold) * 100)
        return {
            "level": "excellent",
            "icon": "mdi:leaf",
            "message": f"Excellent performance (-{saving}% vs. average)",
            "saving_percent": saving,
            "excellent_threshold": excellent_threshold,
            "standard_threshold": standard_threshold,
        }
    elif daily_kwh < standard_threshold:
        return {
            "level": "standard",
            "icon": "mdi:check-circle",
            "message": "Standard performance",
            "saving_percent": 0,
            "excellent_threshold": excellent_threshold,
            "standard_threshold": standard_threshold,
        }
    else:
        excess = round((daily_kwh / standard_threshold - 1) * 100)
        return {
            "level": "to_optimize",
            "icon": "mdi:alert-circle",
            "message": f"Needs optimization (+{excess}% vs. average)",
            "saving_percent": -excess,
            "excellent_threshold": excellent_threshold,
            "standard_threshold": standard_threshold,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Home Performance sensors."""
    coordinator: HomePerformanceCoordinator = hass.data[DOMAIN][entry.entry_id]
    zone_name = coordinator.zone_name

    entities = [
        # Main coefficient
        ThermalLossCoefficientSensor(coordinator, zone_name),
        # Normalized coefficients (only if surface/volume configured)
        KPerM2Sensor(coordinator, zone_name),
        KPerM3Sensor(coordinator, zone_name),
        # Energy (estimated from heater power)
        DailyEnergySensor(coordinator, zone_name),
        # Usage
        HeatingTimeSensor(coordinator, zone_name),
        HeatingRatioSensor(coordinator, zone_name),
        # Performance
        EnergyPerformanceSensor(coordinator, zone_name),
        # Temperature
        DeltaTSensor(coordinator, zone_name),
        # Status
        DataHoursSensor(coordinator, zone_name),
        AnalysisTimeRemainingSensor(coordinator, zone_name),
        AnalysisProgressSensor(coordinator, zone_name),
        InsulationRatingSensor(coordinator, zone_name),
    ]

    # Add measured daily energy sensor if power sensor or energy sensor is configured
    if coordinator.power_sensor or coordinator.energy_sensor:
        entities.append(MeasuredEnergyDailySensor(coordinator, zone_name))

    # Add measured COP sensors if dynamic COP is enabled (heat pumps only)
    if coordinator.enable_dynamic_cop:
        entities.append(MeasuredCOPSensor(coordinator, zone_name))
        entities.append(COP7dSensor(coordinator, zone_name))

    # Diagnostic sensors (always added)
    entities.extend(
        [
            EnergySourceDiagnosticSensor(coordinator, zone_name),
            HeatingDetectionMethodDiagnosticSensor(coordinator, zone_name),
            WindowDetectionMethodDiagnosticSensor(coordinator, zone_name),
            LastKUpdateDiagnosticSensor(coordinator, zone_name),
        ]
    )

    async_add_entities(entities)


class HomePerformanceBaseSensor(CoordinatorEntity[HomePerformanceCoordinator], SensorEntity):
    """Base class for Home Performance sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomePerformanceCoordinator,
        zone_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        self._zone_name = zone_name
        self._sensor_type = sensor_type
        # Use slugify for consistent handling of special characters (ü, é, ç, etc.)
        zone_slug = slugify(zone_name, separator="_")

        # Set unique_id and suggested_object_id BEFORE super().__init__()
        # to ensure they are available when the entity is registered
        self._attr_unique_id = f"home_performance_{zone_slug}_{sensor_type}"

        # Suggest standardized entity_id for new installations
        # Existing users keep their current entity_id via Entity Registry
        suffix = SENSOR_ENTITY_SUFFIXES.get(sensor_type, sensor_type)
        self._attr_suggested_object_id = f"home_performance_{zone_slug}_{suffix}"

        super().__init__(coordinator)

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._zone_name)},
            "name": f"Home Performance - {self._zone_name}",
            "manufacturer": "Home Performance",
            "model": "Thermal Analyzer",
            "sw_version": VERSION,
        }

    def _is_imperial(self) -> bool:
        """Whether the user's HA is configured for Fahrenheit."""
        hass = getattr(self, "hass", None)
        if hass is None:
            return False
        return hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT

    def _convert_abs_temp(self, value_celsius: float) -> float:
        """Convert an absolute temperature (°C → °F with +32 offset)."""
        if self._is_imperial():
            return value_celsius * 9 / 5 + 32
        return value_celsius

    def _convert_delta_temp(self, value_celsius: float) -> float:
        """Convert a temperature delta (°C → °F, no offset)."""
        if self._is_imperial():
            return value_celsius * 9 / 5
        return value_celsius

    def _coordinator_value(self, key: str, round_digits: int | None = None) -> float | None:
        """Read a numeric value from the coordinator data, optionally rounded.

        Returns None when there is no data yet or the key is unset — this is the
        pattern shared by most scalar sensors (so 'no data' shows as Unknown
        instead of a misleading 0).
        """
        data = self.coordinator.data
        if not data:
            return None
        value = data.get(key)
        if value is None:
            return None
        return round(value, round_digits) if round_digits is not None else value


class ScalarCoordinatorSensor(HomePerformanceBaseSensor):
    """Base class for sensors that simply expose one rounded coordinator value.

    Subclasses set ``_data_key`` (the coordinator data key) and may override
    ``_round_digits``. Sensors needing custom attributes/icons still subclass
    this and add their own ``extra_state_attributes``/``icon``.
    """

    _data_key: str
    _round_digits: int | None = 2

    @property
    def native_value(self) -> float | None:
        """Return the (rounded) coordinator value for this sensor."""
        return self._coordinator_value(self._data_key, self._round_digits)


class ThermalLossCoefficientSensor(HomePerformanceBaseSensor):
    """Sensor for thermal loss coefficient K (W/°C)."""

    _attr_native_unit_of_measurement = "W/°C"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:heat-wave"
    _attr_name = "K coefficient"
    # Keep the heavy / static attributes out of the recorder database.
    _unrecorded_attributes = frozenset(
        {"k_history_7d", "description", "interpretation"}
    )

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "k_coefficient")

    @property
    def native_value(self) -> float | None:
        """Return the thermal loss coefficient."""
        if self.coordinator.data:
            value = self.coordinator.data.get("k_coefficient")
            if value is not None:
                return round(value, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        k_24h = data.get("k_coefficient_24h")
        k_7d = data.get("k_coefficient_7d")
        volume = data.get("volume")
        k_per_m3_24h = None
        if k_24h is not None and volume and volume > 0:
            k_per_m3_24h = round(k_24h / volume, 2)

        # K history for sparkline/chart is now precomputed by the coordinator
        # (once per update) to keep this property cheap.
        k_history = data.get("k_history_7d", [])

        # Check if we're at optimal level (Level S)
        insulation_status = data.get("insulation_status", {})
        is_optimal = insulation_status.get("rating") == "optimal"

        # Wind data (if weather entity configured)
        wind_speed = data.get("wind_speed")
        wind_direction = data.get("wind_direction")
        wind_exposure = data.get("wind_exposure")
        room_orientation = data.get("room_orientation")

        return {
            "description": "Thermal loss per degree of temperature difference (W/°C)",
            "heater_power_w": data.get("heater_power"),
            "k_24h": round(k_24h, 1) if k_24h is not None else None,
            "k_7d": round(k_7d, 1) if k_7d is not None else None,
            "k_per_m3_24h": k_per_m3_24h,
            "k_history_7d": k_history,
            "is_optimal": is_optimal,
            # Temperature variation (delta) and min/max (absolute), converted to
            # the user's unit system.
            "temp_variation": (
                round(self._convert_delta_temp(data.get("temp_variation")), 1)
                if data.get("temp_variation") is not None
                else None
            ),
            "indoor_temp_min": (
                round(self._convert_abs_temp(data.get("indoor_temp_min")), 1)
                if data.get("indoor_temp_min") is not None
                else None
            ),
            "indoor_temp_max": (
                round(self._convert_abs_temp(data.get("indoor_temp_max")), 1)
                if data.get("indoor_temp_max") is not None
                else None
            ),
            "temp_unit": "°F" if self._is_imperial() else "°C",
            "interpretation": (
                "Lower K = better insulation. "
                "Typical values: 10-20 (well insulated), 20-40 (average), 40+ (poorly insulated)"
            ),
            # Weather data (wind)
            "wind_speed": round(wind_speed, 1) if wind_speed is not None else None,
            "wind_speed_unit": data.get("wind_speed_unit"),
            "wind_direction": wind_direction,
            "wind_bearing": data.get("wind_bearing"),
            "wind_exposure": wind_exposure,
            "room_orientation": room_orientation,
        }


class KPerM2Sensor(ScalarCoordinatorSensor):
    """Sensor for K normalized by surface (W/(°C·m²))."""

    _attr_native_unit_of_measurement = "W/(°C·m²)"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:square-outline"
    _attr_name = "K per m²"
    _data_key = "k_per_m2"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "k_per_m2")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "description": "K normalized by surface area - comparable between rooms",
            "surface_m2": data.get("surface"),
        }


class KPerM3Sensor(ScalarCoordinatorSensor):
    """Sensor for K normalized by volume (W/(°C·m³))."""

    _attr_native_unit_of_measurement = "W/(°C·m³)"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cube-outline"
    _attr_name = "K per m³"
    _data_key = "k_per_m3"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "k_per_m3")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "description": "K normalized by volume - better for comparing rooms with different ceiling heights",
            "volume_m3": data.get("volume"),
        }


class DailyEnergySensor(ScalarCoordinatorSensor):
    """Sensor for daily energy consumption (rolling 24h window, estimated).

    Uses state_class TOTAL (not TOTAL_INCREASING) because this is a daily
    counter that resets at midnight, similar to a Utility Meter.
    """

    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:lightning-bolt-outline"
    _attr_name = "Daily estimated energy"
    _data_key = "daily_energy_kwh"
    _round_digits = 3

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "daily_energy")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "description": "Estimated energy over the last rolling 24h",
            "heater_power_w": data.get("heater_power"),
            "calculation": "estimation",
            "window": "24h glissantes",
            "heating_hours": (round(data.get("heating_hours"), 1) if data.get("heating_hours") is not None else None),
        }


class HeatingTimeSensor(ScalarCoordinatorSensor):
    """Sensor for heating time over 24h."""

    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_icon = "mdi:clock-outline"
    _attr_name = "Heating time 24h"
    _data_key = "heating_hours"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "heating_time")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        hours = data.get("heating_hours")
        # Source: power sensor (measured) or switch/climate state (estimated)
        has_power_sensor = self.coordinator.power_sensor is not None
        power_threshold = self.coordinator.power_threshold
        return {
            "formatted": format_duration(hours),
            "source": "measured" if has_power_sensor else "estimated",
            "detection": (
                f"power > {power_threshold}W ({self.coordinator.power_sensor})"
                if has_power_sensor
                else f"state of {self.coordinator.heating_entity}"
            ),
            "power_threshold_w": power_threshold if has_power_sensor else None,
            "description": "Cumulative heating time over the last 24h",
        }


class HeatingRatioSensor(HomePerformanceBaseSensor):
    """Sensor for heating ratio (% of time heating is on)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:percent"
    _attr_name = "Heating ratio 24h"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "heating_ratio")

    @property
    def native_value(self) -> float | None:
        """Return heating ratio as percentage."""
        if self.coordinator.data:
            value = self.coordinator.data.get("heating_ratio")
            if value is not None:
                return round(value * 100, 0)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        has_power_sensor = self.coordinator.power_sensor is not None
        power_threshold = self.coordinator.power_threshold
        return {
            "description": "Percentage of time heating is active over 24h",
            "source": "measured" if has_power_sensor else "estimated",
            "power_threshold_w": power_threshold if has_power_sensor else None,
        }


class EnergyPerformanceSensor(HomePerformanceBaseSensor):
    """Sensor for energy performance evaluation based on French national statistics."""

    _attr_icon = "mdi:leaf"
    _attr_name = "Energy performance"
    _unrecorded_attributes = frozenset({"description"})

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "energy_performance")
        self._perf_cache_key: tuple | None = None
        self._perf_cache: dict[str, Any] | None = None

    def _perf(self) -> dict[str, Any] | None:
        """Compute energy performance once per coordinator update (memoized).

        native_value, icon and extra_state_attributes all need this; without a
        cache it would run three times per refresh.
        """
        if not self.coordinator.data:
            return None
        daily_kwh = self.coordinator.data.get("daily_energy_kwh")
        heater_power = self.coordinator.data.get("heater_power")
        derived_power = self.coordinator.data.get("derived_power")
        key = (daily_kwh, heater_power, derived_power)
        if key != self._perf_cache_key:
            self._perf_cache_key = key
            self._perf_cache = get_energy_performance(daily_kwh, heater_power, derived_power)
        return self._perf_cache

    @property
    def native_value(self) -> str | None:
        """Return energy performance level."""
        perf = self._perf()
        return perf.get("level") if perf else None

    @property
    def icon(self) -> str:
        """Return dynamic icon based on performance level."""
        perf = self._perf()
        return perf.get("icon", "mdi:help-circle") if perf else "mdi:help-circle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        daily_kwh = data.get("daily_energy_kwh")
        heater_power = data.get("heater_power")
        derived_power = data.get("derived_power")
        perf = self._perf() or {}

        level_descriptions = {
            "excellent": "🟢 Excellent",
            "standard": "🟡 Standard",
            "to_optimize": "🟠 Needs optimization",
        }

        return {
            "message": perf.get("message"),
            "level_display": level_descriptions.get(perf.get("level"), "En attente"),
            "saving_percent": perf.get("saving_percent"),
            "excellent_threshold_kwh": (
                round(perf.get("excellent_threshold"), 1) if perf.get("excellent_threshold") is not None else None
            ),
            "standard_threshold_kwh": (
                round(perf.get("standard_threshold"), 1) if perf.get("standard_threshold") is not None else None
            ),
            "daily_energy_kwh": round(daily_kwh, 2) if daily_kwh is not None else None,
            "heater_power_w": heater_power,
            "derived_power_w": round(derived_power, 0) if derived_power else None,
            "effective_power_w": heater_power if heater_power else (round(derived_power, 0) if derived_power else None),
            "description": (
                "Evaluation based on national statistics. "
                "Thresholds calculated based on heater power (or derived power for energy-based sources)."
            ),
        }


class DeltaTSensor(HomePerformanceBaseSensor):
    """Sensor for average temperature difference.

    Note: No device_class=TEMPERATURE because this is a temperature DIFFERENCE,
    not an absolute temperature. HA's conversion formula (°F = °C × 9/5 + 32)
    would give wrong results for deltas (should be Δ°F = Δ°C × 9/5, no +32).

    We handle the conversion manually based on the user's unit system.
    """

    # No device_class - this is a temperature delta, not absolute temperature
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"
    _attr_name = "Avg delta T 24h"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "avg_delta_t")

    def _convert_delta(self, value_celsius: float) -> float:
        """Convert temperature delta to user's unit system (no +32 offset)."""
        return self._convert_delta_temp(value_celsius)

    def _convert_abs(self, value_celsius: float) -> float:
        """Convert an absolute temperature (°C → °F with +32 offset)."""
        return self._convert_abs_temp(value_celsius)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit based on user's system."""
        return "°F" if self._is_imperial() else "°C"

    @property
    def native_value(self) -> float | None:
        """Return average ΔT in user's unit system."""
        if self.coordinator.data:
            value = self.coordinator.data.get("avg_delta_t")
            if value is not None:
                return round(self._convert_delta(value), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        current_dt = data.get("delta_t")

        return {
            "description": "Average temperature difference between indoor and outdoor (rolling 24h window)",
            "window": "rolling 24h",
            "current_delta_t": (round(self._convert_delta(current_dt), 1) if current_dt is not None else None),
            "indoor_temp": (
                round(self._convert_abs(data.get("indoor_temp")), 1) if data.get("indoor_temp") is not None else None
            ),
            "outdoor_temp": (
                round(self._convert_abs(data.get("outdoor_temp")), 1) if data.get("outdoor_temp") is not None else None
            ),
            "temp_unit": "°F" if self._is_imperial() else "°C",
            "unit_note": "Temperature delta (not absolute) - correctly converted for your unit system",
        }


class DataHoursSensor(ScalarCoordinatorSensor):
    """Sensor for hours of data collected."""

    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_icon = "mdi:database-clock"
    _attr_name = "Data hours"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _data_key = "data_hours"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "data_hours")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        hours = data.get("data_hours")
        return {
            "formatted": format_duration(hours),
            "samples_count": data.get("samples_count"),
            "data_ready": data.get("data_ready"),
            "min_hours_required": MIN_DATA_HOURS,
        }


class AnalysisTimeRemainingSensor(HomePerformanceBaseSensor):
    """Sensor for remaining time before data is ready."""

    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_icon = "mdi:timer-sand"
    _attr_name = "Analysis remaining"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "analysis_remaining")

    @property
    def native_value(self) -> float:
        """Return remaining time in hours (decimal). Returns 0 when ready."""
        data_hours = 0
        data_ready = False

        if self.coordinator.data:
            data_hours = self.coordinator.data.get("data_hours", 0) or 0
            data_ready = self.coordinator.data.get("data_ready", False)

        if data_ready:
            return 0.0

        remaining = max(0, MIN_DATA_HOURS - data_hours)
        return round(remaining, 2)

    @property
    def icon(self) -> str:
        """Return dynamic icon based on status."""
        if self.coordinator.data and self.coordinator.data.get("data_ready"):
            return "mdi:check-circle"
        return "mdi:timer-sand"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        data_hours = data.get("data_hours", 0) or 0
        data_ready = data.get("data_ready", False)
        remaining = max(0, MIN_DATA_HOURS - data_hours)
        progress_pct = min(100, round((data_hours / MIN_DATA_HOURS) * 100))

        return {
            "formatted": format_duration(remaining) if not data_ready else "Ready",
            "remaining_minutes": round(remaining * 60) if not data_ready else 0,
            "progress_percent": 100 if data_ready else progress_pct,
            "data_ready": data_ready,
            "hours_collected": round(data_hours, 2),
            "hours_required": MIN_DATA_HOURS,
        }


class AnalysisProgressSensor(HomePerformanceBaseSensor):
    """Sensor for analysis progress percentage (0-100)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:progress-clock"
    _attr_name = "Analysis progress"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "analysis_progress")

    @property
    def native_value(self) -> int:
        """Return analysis progress as percentage (0-100)."""
        if self.coordinator.data:
            data_hours = self.coordinator.data.get("data_hours", 0) or 0
            data_ready = self.coordinator.data.get("data_ready", False)

            if data_ready:
                return 100

            return min(100, round((data_hours / MIN_DATA_HOURS) * 100))
        return 0

    @property
    def icon(self) -> str:
        """Return dynamic icon based on progress."""
        if self.coordinator.data:
            data_ready = self.coordinator.data.get("data_ready", False)
            if data_ready:
                return "mdi:check-circle"

            progress = self.native_value
            if progress < 25:
                return "mdi:circle-outline"
            elif progress < 50:
                return "mdi:circle-slice-2"
            elif progress < 75:
                return "mdi:circle-slice-4"
            else:
                return "mdi:circle-slice-6"
        return "mdi:circle-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        data_hours = data.get("data_hours", 0) or 0
        data_ready = data.get("data_ready", False)

        return {
            "hours_collected": round(data_hours, 2),
            "hours_required": MIN_DATA_HOURS,
            "data_ready": data_ready,
            "description": "Data collection progress (0-100%)",
        }


class InsulationRatingSensor(HomePerformanceBaseSensor):
    """Sensor for insulation rating (qualitative).

    Handles multiple scenarios:
    - Calculated rating from K coefficient
    - Inferred excellent rating (minimal heating needed)
    - Off-season/summer mode (preserve last valid rating)
    """

    _attr_icon = "mdi:home-thermometer"
    _attr_name = "Insulation rating"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "insulation_rating")

    @property
    def native_value(self) -> str | None:
        """Return insulation rating.

        Priority:
        1. Calculated rating from K coefficient
        2. Inferred excellent rating
        3. Last valid rating (during off-season)
        """
        if self.coordinator.data:
            insulation_status = self.coordinator.data.get("insulation_status", {})
            rating = insulation_status.get("rating")
            if rating:
                return rating
            # Fallback to old method for compatibility
            return self.coordinator.data.get("insulation_rating")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        insulation_status = data.get("insulation_status", {})

        rating = insulation_status.get("rating") or data.get("insulation_rating")
        status = insulation_status.get("status", "waiting_data")
        season = insulation_status.get("season", "heating_season")
        k_source = insulation_status.get("k_source")
        message = insulation_status.get("message")
        k_value = insulation_status.get("k_value")

        rating_descriptions = {
            "optimal": "Level S - Optimal performance",
            "excellent": "Very well insulated",
            "excellent_inferred": "Excellent (inferred)",
            "good": "Well insulated",
            "average": "Average insulation",
            "poor": "Poorly insulated",
            "very_poor": "Very poorly insulated / thermal bridge",
        }

        season_descriptions = {
            "summer": "☀️ Summer mode",
            "off_season": "🌤️ Shoulder season",
            "heating_season": "❄️ Heating season",
        }

        return {
            "description": rating_descriptions.get(rating, message or "Waiting for data"),
            "status": status,
            "season": season,
            "season_description": season_descriptions.get(season, season),
            "k_value": round(k_value, 1) if k_value is not None else None,
            "k_source": k_source,
            "k_per_m3": (round(data.get("k_per_m3"), 2) if data.get("k_per_m3") is not None else None),
            "last_k_date": data.get("last_k_date"),
            "temp_stable": insulation_status.get("temp_stable"),
            "message": message,
            "note": "Based on K/m³ or inferred if minimal heating needed",
        }


class MeasuredEnergyDailySensor(HomePerformanceBaseSensor):
    """Sensor for daily measured energy.

    Priority:
    1. External energy sensor (if configured) - uses user's own HA energy counter
    2. Integrated calculation from power sensor

    This sensor behaves like a Utility Meter (Compteur de services publics):
    - state_class: TOTAL (not TOTAL_INCREASING)
    - last_reset: datetime of last midnight reset
    """

    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:counter"
    _attr_name = "Daily measured energy"
    _unrecorded_attributes = frozenset({"description"})

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "measured_energy_daily")

    @property
    def native_value(self) -> float | None:
        """Return daily measured energy in kWh.

        Uses external energy sensor if configured, otherwise uses internal calculation.
        """
        if self.coordinator.data:
            # Priority 1: External energy sensor
            external = self.coordinator.data.get("external_energy_daily_kwh")
            if external is not None:
                return round(external, 3)

            # Priority 2: Internal calculation from power sensor
            value = self.coordinator.data.get("measured_energy_daily_kwh")
            if value is not None:
                return round(value, 3)
        # No data yet: report unknown rather than a misleading 0 kWh that would
        # pollute long-term statistics.
        return None

    @property
    def last_reset(self):
        """Return the time when the sensor was last reset (midnight).

        This is required for Utility Meter compatibility.
        Only applies to internal calculation, not external sensor.
        """
        # If using external sensor, don't report last_reset (external handles it)
        if self.coordinator.data and self.coordinator.data.get("external_energy_daily_kwh") is not None:
            return None
        if self.coordinator.data:
            return self.coordinator.data.get("daily_reset_datetime")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        uses_external = data.get("external_energy_daily_kwh") is not None
        return {
            "description": "Daily energy counter",
            "source": "external" if uses_external else "integrated",
            "energy_sensor": self.coordinator.energy_sensor if uses_external else None,
            "power_sensor": self.coordinator.power_sensor if not uses_external else None,
            "current_power_w": data.get("measured_power_w") if not uses_external else None,
        }


class MeasuredCOPSensor(HomePerformanceBaseSensor):
    """Sensor for measured COP (Coefficient of Performance) for heat pumps.

    Calculates real-world COP based on:
    - K coefficient (thermal loss)
    - Temperature difference (ΔT)
    - Heating time
    - Actual energy consumption (from energy sensor)

    Formula: COP = Thermal_energy_output / Electrical_energy_input
    Where: Thermal_energy = K × ΔT × hours
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:heat-pump"
    _attr_name = "Measured COP"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "measured_cop")

    @property
    def native_value(self) -> float | None:
        """Return the measured COP value."""
        if self.coordinator.data:
            cop = self.coordinator.data.get("measured_cop")
            if cop is not None:
                return round(cop, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        cop_status = data.get("cop_status")

        # Map status to user-friendly messages
        status_messages = {
            "ok": "COP calculated successfully",
            "waiting_calibration": "Waiting for K coefficient calibration",
            "insufficient_delta_t": "Temperature difference too low (need ΔT ≥ 5°C)",
            "insufficient_heating_time": "Not enough heating time (need ≥ 30 min)",
            "no_energy_data": "No energy consumption data",
            "low_cop_warning": "COP unusually low - check sensor configuration",
            "high_cop_warning": "COP unusually high - check sensor configuration",
            "waiting_data": "Waiting for measurement data",
        }

        return {
            "description": "Real-time COP calculated from actual measurements",
            "status": cop_status,
            "status_message": status_messages.get(cop_status, "Unknown status"),
            "static_efficiency_factor": self.coordinator.efficiency_factor,
            "k_coefficient": data.get("k_coefficient"),
            "avg_delta_t": data.get("avg_delta_t"),
            "heating_hours": data.get("heating_hours"),
            "energy_consumed_kwh": data.get("external_energy_daily_kwh"),
            "note": "COP = Thermal output / Electrical input. Typical values: 2.5-4.5",
        }


class COP7dSensor(HomePerformanceBaseSensor):
    """Sensor for 7-day average COP (used for auto-calibration).

    This sensor shows the rolling 7-day average of measured COP values.
    When dynamic COP is enabled, this value is used as the effective
    efficiency factor for K coefficient calculations instead of the
    static factor configured in settings.

    This provides automatic adaptation to:
    - Seasonal variations (COP changes with outdoor temperature)
    - Heat pump performance changes over time
    - Different operating conditions
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-line"
    _attr_name = "COP 7d Average"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "cop_7d")

    @property
    def native_value(self) -> float | None:
        """Return the 7-day average COP value."""
        if self.coordinator.data:
            cop_7d = self.coordinator.data.get("cop_7d")
            if cop_7d is not None:
                return round(cop_7d, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}

        # Determine status
        cop_7d = data.get("cop_7d")
        measured_cop = data.get("measured_cop")
        static_factor = self.coordinator.efficiency_factor

        if cop_7d is not None:
            status = "active"
            status_message = "Using COP 7d for K calculations"
        elif measured_cop is not None:
            status = "collecting"
            status_message = "Collecting data (need 3+ days with valid COP)"
        else:
            status = "waiting"
            status_message = "Waiting for first COP measurement"

        return {
            "description": "7-day rolling average COP used for K calculations",
            "status": status,
            "status_message": status_message,
            "static_efficiency_factor": static_factor,
            "effective_efficiency": data.get("effective_efficiency"),
            "measured_cop_24h": measured_cop,
            "days_with_cop_data": self._count_days_with_cop(),
            "is_active": cop_7d is not None,
            "note": "After 3+ days of valid COP data, this value replaces the static factor",
        }

    def _count_days_with_cop(self) -> int:
        """Count days in history with valid COP measurements."""
        history = self.coordinator.thermal_model.daily_history
        return sum(1 for entry in history if entry.measured_cop is not None and entry.measured_cop > 0)


# =============================================================================
# Diagnostic sensors (EntityCategory.DIAGNOSTIC)
# =============================================================================


class EnergySourceDiagnosticSensor(HomePerformanceBaseSensor):
    """Diagnostic sensor showing which energy source is active for K calculation.

    Priority: energy_sensor > power_sensor > heater_power (estimation)
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:flash-alert"
    _attr_name = "Energy source"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "energy_source")

    @property
    def native_value(self) -> str | None:
        """Return the active energy source."""
        if not self.coordinator.data:
            return None
        data = self.coordinator.data
        if data.get("energy_sensor_configured") and data.get("external_energy_daily_kwh") is not None:
            return "energy_sensor"
        if data.get("power_sensor_configured") and data.get("measured_energy_daily_kwh") is not None:
            return "power_sensor"
        if data.get("heater_power"):
            return "heater_power"
        return "none"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "energy_sensor": self.coordinator.energy_sensor,
            "power_sensor": self.coordinator.power_sensor,
            "heater_power_w": data.get("heater_power"),
            "description": "Active energy source used for K coefficient calculation (priority: energy_sensor > power_sensor > heater_power)",
        }


class HeatingDetectionMethodDiagnosticSensor(HomePerformanceBaseSensor):
    """Diagnostic sensor showing how heating state is detected."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:radiator"
    _attr_name = "Heating detection method"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "heating_detection_method")

    @property
    def native_value(self) -> str:
        """Return the heating detection method."""
        if self.coordinator.power_sensor:
            return "power_sensor"
        domain = self.coordinator.heating_entity.split(".")[0]
        if domain == "climate":
            return "climate_hvac_action"
        if domain in ("select", "input_select"):
            return "select_state"
        return "entity_state"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        method = self.native_value

        method_descriptions = {
            "power_sensor": f"Power > {self.coordinator.power_threshold}W threshold on {self.coordinator.power_sensor}",
            "climate_hvac_action": f"hvac_action attribute on {self.coordinator.heating_entity}",
            "select_state": f"State in {self.coordinator.heating_active_states} on {self.coordinator.heating_entity}",
            "entity_state": f"on/off state of {self.coordinator.heating_entity}",
        }

        return {
            "heating_entity": self.coordinator.heating_entity,
            "power_sensor": self.coordinator.power_sensor,
            "power_threshold_w": self.coordinator.power_threshold if self.coordinator.power_sensor else None,
            "description": method_descriptions.get(method, method),
        }


class WindowDetectionMethodDiagnosticSensor(HomePerformanceBaseSensor):
    """Diagnostic sensor showing how window open state is detected."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:window-open-variant"
    _attr_name = "Window detection method"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "window_detection_method")

    @property
    def native_value(self) -> str:
        """Return the window detection method."""
        if self.coordinator.window_sensor:
            return "sensor"
        return "temperature"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.window_sensor:
            return {
                "window_sensor": self.coordinator.window_sensor,
                "description": f"Using physical sensor {self.coordinator.window_sensor}",
            }
        return {
            "description": "Detecting window open via rapid temperature drops (no physical sensor configured)",
        }


class LastKUpdateDiagnosticSensor(HomePerformanceBaseSensor):
    """Diagnostic sensor showing the date of the last valid K coefficient update."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:calendar-clock"
    _attr_name = "Last K update"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "last_k_update")

    @property
    def native_value(self) -> str | None:
        """Return the date of the last K coefficient update (ISO format)."""
        return self.coordinator.thermal_model.last_k_date

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        history = self.coordinator.thermal_model.daily_history
        return {
            "history_days": len(history),
            "samples_count": data.get("samples_count", 0),
            "data_hours": data.get("data_hours", 0),
            "description": "Date when the K coefficient was last successfully calculated",
        }
