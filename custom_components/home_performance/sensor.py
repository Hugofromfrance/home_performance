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
from homeassistant.const import UnitOfTime, UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.slugify import slugify

from .const import DOMAIN, CONF_ZONE_NAME, VERSION
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


def get_energy_performance(daily_kwh: float | None, heater_power_w: float) -> dict[str, Any]:
    """
    Evaluate energy performance based on French national statistics.

    Thresholds based on heater power:
    - Excellent: < (power/1000) * 4 kWh/day (-40% vs national average)
    - Standard: between excellent and (power/1000) * 6 kWh/day
    - To optimize: > (power/1000) * 6 kWh/day
    """
    if daily_kwh is None or heater_power_w <= 0:
        return {
            "level": None,
            "icon": "mdi:help-circle",
            "message": "Waiting for data",
            "saving_percent": None,
            "excellent_threshold": None,
            "standard_threshold": None,
        }

    # Thresholds based on heater power
    excellent_threshold = (heater_power_w / 1000) * 4
    standard_threshold = (heater_power_w / 1000) * 6

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
        super().__init__(coordinator)
        self._zone_name = zone_name
        self._sensor_type = sensor_type
        # Use slugify for consistent handling of special characters (ü, é, ç, etc.)
        zone_slug = slugify(zone_name, separator="_")
        self._attr_unique_id = f"home_performance_{zone_slug}_{sensor_type}"

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


class ThermalLossCoefficientSensor(HomePerformanceBaseSensor):
    """Sensor for thermal loss coefficient K (W/°C)."""

    _attr_native_unit_of_measurement = "W/°C"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:heat-wave"
    _attr_translation_key = "coefficient_k"

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

        # Build K history for sparkline/chart visualization (7 days)
        # Strategy: Use K_7j (rolling average) for each day to match the displayed score
        # This shows how the score EVOLVED over time, not daily fluctuations
        history = self.coordinator.thermal_model.daily_history
        heater_power = self.coordinator.heater_power
        current_k_7d = k_7d  # Current K_7j (for today and fallback)

        # Create a dict of history entries by date for easy lookup
        history_by_date = {entry.date: entry for entry in history}

        # Generate last 7 days
        from datetime import datetime, timedelta
        today = datetime.now().date()

        # First pass: get K_7j for each day (stored at archival time)
        days_data = []
        for i in range(6, -1, -1):  # 6 days ago to today
            day = today - timedelta(days=i)
            date_str = day.strftime("%Y-%m-%d")
            entry = history_by_date.get(date_str)

            k_value = None
            is_today = (i == 0)

            if is_today:
                # Today: use current K_7j (not yet archived)
                k_value = current_k_7d
            elif entry:
                # Historical day: prefer stored K_7j, fallback to calculated K_daily
                if entry.k_7d is not None:
                    k_value = entry.k_7d
                elif entry.avg_delta_t >= 5 and entry.heating_hours >= 0.5:
                    # Fallback for old data without k_7d: calculate daily K
                    energy_wh = heater_power * entry.heating_hours
                    k_value = energy_wh / (entry.avg_delta_t * 24)

            days_data.append({
                "date": date_str,
                "k": k_value,  # None if no valid data
            })

        # Second pass: fill gaps using carry-forward and backfill
        # Forward pass: carry-forward from first valid day
        last_valid_k = None
        for day_data in days_data:
            if day_data["k"] is not None:
                last_valid_k = day_data["k"]
            elif last_valid_k is not None:
                day_data["k"] = last_valid_k
                day_data["estimated"] = True

        # Backward pass: backfill days before first valid day with first valid K
        first_valid_k = None
        for day_data in days_data:
            if day_data["k"] is not None and "estimated" not in day_data:
                first_valid_k = day_data["k"]
                break

        if first_valid_k is not None:
            for day_data in days_data:
                if day_data["k"] is None:
                    day_data["k"] = first_valid_k
                    day_data["estimated"] = True

        # Build final k_history (only include days with K values)
        k_history = []
        for day_data in days_data:
            if day_data["k"] is not None:
                k_history.append({
                    "date": day_data["date"],
                    "k": round(day_data["k"], 1),
                    "estimated": day_data.get("estimated", False)
                })

        return {
            "description": "Thermal loss per degree of temperature difference (W/°C)",
            "heater_power_w": data.get("heater_power"),
            "k_24h": round(k_24h, 1) if k_24h is not None else None,
            "k_7d": round(k_7d, 1) if k_7d is not None else None,
            "k_per_m3_24h": k_per_m3_24h,
            "k_history_7d": k_history,
            "interpretation": (
                "Lower K = better insulation. "
                "Typical values: 10-20 (well insulated), 20-40 (average), 40+ (poorly insulated)"
            ),
        }


class KPerM2Sensor(HomePerformanceBaseSensor):
    """Sensor for K normalized by surface (W/(°C·m²))."""

    _attr_native_unit_of_measurement = "W/(°C·m²)"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:square-outline"
    _attr_translation_key = "k_par_m2"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "k_per_m2")

    @property
    def native_value(self) -> float | None:
        """Return K/m²."""
        if self.coordinator.data:
            value = self.coordinator.data.get("k_per_m2")
            if value is not None:
                return round(value, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "description": "K normalized by surface area - comparable between rooms",
            "surface_m2": data.get("surface"),
        }


class KPerM3Sensor(HomePerformanceBaseSensor):
    """Sensor for K normalized by volume (W/(°C·m³))."""

    _attr_native_unit_of_measurement = "W/(°C·m³)"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cube-outline"
    _attr_translation_key = "k_par_m3"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "k_per_m3")

    @property
    def native_value(self) -> float | None:
        """Return K/m³."""
        if self.coordinator.data:
            value = self.coordinator.data.get("k_per_m3")
            if value is not None:
                return round(value, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "description": "K normalized by volume - better for comparing rooms with different ceiling heights",
            "volume_m3": data.get("volume"),
        }


class DailyEnergySensor(HomePerformanceBaseSensor):
    """Sensor for daily energy consumption (rolling 24h window, estimated)."""

    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt-outline"
    _attr_translation_key = "energie_estimee_journaliere"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "daily_energy")

    @property
    def native_value(self) -> float | None:
        """Return daily energy in kWh."""
        if self.coordinator.data:
            value = self.coordinator.data.get("daily_energy_kwh")
            if value is not None:
                return round(value, 3)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "description": "Estimated energy over the last rolling 24h",
            "heater_power_w": data.get("heater_power"),
            "calculation": "estimation",
            "window": "24h glissantes",
            "heating_hours": (
                round(data.get("heating_hours"), 1)
                if data.get("heating_hours") is not None
                else None
            ),
        }


class HeatingTimeSensor(HomePerformanceBaseSensor):
    """Sensor for heating time over 24h."""

    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_icon = "mdi:clock-outline"
    _attr_translation_key = "temps_de_chauffe_24h"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "heating_time")

    @property
    def native_value(self) -> float | None:
        """Return heating time in hours (decimal)."""
        if self.coordinator.data:
            value = self.coordinator.data.get("heating_hours")
            if value is not None:
                return round(value, 2)
        return None

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
            "detection": f"power > {power_threshold}W ({self.coordinator.power_sensor})" if has_power_sensor else f"state of {self.coordinator.heating_entity}",
            "power_threshold_w": power_threshold if has_power_sensor else None,
            "description": "Cumulative heating time over the last 24h",
        }


class HeatingRatioSensor(HomePerformanceBaseSensor):
    """Sensor for heating ratio (% of time heating is on)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:percent"
    _attr_translation_key = "taux_de_chauffe_24h"

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
    _attr_translation_key = "performance_energetique"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "energy_performance")

    @property
    def native_value(self) -> str | None:
        """Return energy performance level."""
        if self.coordinator.data:
            daily_kwh = self.coordinator.data.get("daily_energy_kwh")
            heater_power = self.coordinator.data.get("heater_power", 0)
            perf = get_energy_performance(daily_kwh, heater_power)
            return perf.get("level")
        return None

    @property
    def icon(self) -> str:
        """Return dynamic icon based on performance level."""
        if self.coordinator.data:
            daily_kwh = self.coordinator.data.get("daily_energy_kwh")
            heater_power = self.coordinator.data.get("heater_power", 0)
            perf = get_energy_performance(daily_kwh, heater_power)
            return perf.get("icon", "mdi:help-circle")
        return "mdi:help-circle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        daily_kwh = data.get("daily_energy_kwh")
        heater_power = data.get("heater_power", 0)
        perf = get_energy_performance(daily_kwh, heater_power)

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
                round(perf.get("excellent_threshold"), 1)
                if perf.get("excellent_threshold") is not None
                else None
            ),
            "standard_threshold_kwh": (
                round(perf.get("standard_threshold"), 1)
                if perf.get("standard_threshold") is not None
                else None
            ),
            "daily_energy_kwh": round(daily_kwh, 2) if daily_kwh is not None else None,
            "heater_power_w": heater_power,
            "description": (
                "Evaluation based on national statistics. "
                "Thresholds calculated based on heater power."
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
    _attr_translation_key = "dt_moyen_24h"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "avg_delta_t")

    def _is_imperial(self) -> bool:
        """Check if user's HA is configured for imperial (Fahrenheit)."""
        return self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT

    def _convert_delta(self, value_celsius: float) -> float:
        """Convert temperature delta to user's unit system.

        For deltas: Δ°F = Δ°C × 9/5 (no +32 offset!)
        """
        if self._is_imperial():
            return value_celsius * 9 / 5
        return value_celsius

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
            "current_delta_t": (
                round(self._convert_delta(current_dt), 1)
                if current_dt is not None
                else None
            ),
            "indoor_temp": (
                round(data.get("indoor_temp"), 1)
                if data.get("indoor_temp") is not None
                else None
            ),
            "outdoor_temp": (
                round(data.get("outdoor_temp"), 1)
                if data.get("outdoor_temp") is not None
                else None
            ),
            "unit_note": "Temperature delta (not absolute) - correctly converted for your unit system",
        }


class DataHoursSensor(HomePerformanceBaseSensor):
    """Sensor for hours of data collected."""

    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_icon = "mdi:database-clock"
    _attr_translation_key = "heures_de_donnees"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "data_hours")

    @property
    def native_value(self) -> float | None:
        """Return hours of data collected (decimal)."""
        if self.coordinator.data:
            value = self.coordinator.data.get("data_hours")
            if value is not None:
                return round(value, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        hours = data.get("data_hours")
        return {
            "formatted": format_duration(hours),
            "samples_count": data.get("samples_count"),
            "data_ready": data.get("data_ready"),
            "min_hours_required": 12,
        }


class AnalysisTimeRemainingSensor(HomePerformanceBaseSensor):
    """Sensor for remaining time before data is ready."""

    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_icon = "mdi:timer-sand"
    _attr_translation_key = "temps_d_analyse_restant"

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

        remaining = max(0, 12 - data_hours)
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
        remaining = max(0, 12 - data_hours)
        progress_pct = min(100, round((data_hours / 12) * 100))

        return {
            "formatted": format_duration(remaining) if not data_ready else "Ready",
            "remaining_minutes": round(remaining * 60) if not data_ready else 0,
            "progress_percent": 100 if data_ready else progress_pct,
            "data_ready": data_ready,
            "hours_collected": round(data_hours, 2),
            "hours_required": 12,
        }


class AnalysisProgressSensor(HomePerformanceBaseSensor):
    """Sensor for analysis progress percentage (0-100)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:progress-clock"
    _attr_translation_key = "progression_analyse"

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

            return min(100, round((data_hours / 12) * 100))
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
            "hours_required": 12,
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
    _attr_translation_key = "note_d_isolation"

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
            "excellent": "Very well insulated",
            "excellent_inferred": "🏆 Excellent (inferred)",
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
            "k_per_m3": (
                round(data.get("k_per_m3"), 2)
                if data.get("k_per_m3") is not None
                else None
            ),
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
    _attr_translation_key = "energie_mesuree_journaliere"

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
        return 0.0

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


