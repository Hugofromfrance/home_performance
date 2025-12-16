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
from homeassistant.const import UnitOfTime, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ZONE_NAME
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
            "message": "En attente de données",
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
            "message": f"Performance excellente (-{saving}% vs. moyenne)",
            "saving_percent": saving,
            "excellent_threshold": excellent_threshold,
            "standard_threshold": standard_threshold,
        }
    elif daily_kwh < standard_threshold:
        return {
            "level": "standard",
            "icon": "mdi:check-circle",
            "message": "Performance standard",
            "saving_percent": 0,
            "excellent_threshold": excellent_threshold,
            "standard_threshold": standard_threshold,
        }
    else:
        excess = round((daily_kwh / standard_threshold - 1) * 100)
        return {
            "level": "to_optimize",
            "icon": "mdi:alert-circle",
            "message": f"Marge d'optimisation (+{excess}% vs. moyenne)",
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
        # Energy and usage (estimated from heater power)
        TotalEnergySensor(coordinator, zone_name),  # Cumulative - Energy Dashboard compatible
        DailyEnergySensor(coordinator, zone_name),
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

    # Add measured energy sensors if power sensor or energy sensor is configured
    if coordinator.power_sensor or coordinator.energy_sensor:
        entities.extend([
            MeasuredEnergyDailySensor(coordinator, zone_name),
            MeasuredEnergyTotalSensor(coordinator, zone_name),
        ])

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
        self._attr_unique_id = (
            f"home_performance_{zone_name}_{sensor_type}".lower().replace(" ", "_")
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._zone_name)},
            "name": f"Home Performance - {self._zone_name}",
            "manufacturer": "Home Performance",
            "model": "Thermal Analyzer",
            "sw_version": "1.0.0",
        }


class ThermalLossCoefficientSensor(HomePerformanceBaseSensor):
    """Sensor for thermal loss coefficient K (W/°C)."""

    _attr_native_unit_of_measurement = "W/°C"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:heat-wave"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "k_coefficient")
        self._attr_name = "Coefficient K"

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
        return {
            "description": "Déperdition thermique par degré d'écart (W/°C)",
            "heater_power_w": data.get("heater_power"),
            "interpretation": (
                "Plus K est bas, meilleure est l'isolation. "
                "Valeurs typiques: 10-20 (bien isolé), 20-40 (moyen), 40+ (mal isolé)"
            ),
        }


class KPerM2Sensor(HomePerformanceBaseSensor):
    """Sensor for K normalized by surface (W/(°C·m²))."""

    _attr_native_unit_of_measurement = "W/(°C·m²)"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:square-outline"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "k_per_m2")
        self._attr_name = "K par m²"

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
            "description": "K normalisé par surface - comparable entre pièces",
            "surface_m2": data.get("surface"),
        }


class KPerM3Sensor(HomePerformanceBaseSensor):
    """Sensor for K normalized by volume (W/(°C·m³))."""

    _attr_native_unit_of_measurement = "W/(°C·m³)"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cube-outline"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "k_per_m3")
        self._attr_name = "K par m³"

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
            "description": "K normalisé par volume - meilleur pour comparer des pièces de hauteurs différentes",
            "volume_m3": data.get("volume"),
        }


class TotalEnergySensor(HomePerformanceBaseSensor):
    """Sensor for total cumulative energy (estimated from declared power)."""

    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:lightning-bolt-outline"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "total_energy")
        self._attr_name = "Énergie totale (estimée)"

    @property
    def native_value(self) -> float | None:
        """Return total cumulative energy in kWh."""
        if self.coordinator.data:
            value = self.coordinator.data.get("total_energy_kwh")
            if value is not None:
                return round(value, 3)
        return 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "description": "Énergie estimée (puissance déclarée × temps ON)",
            "heater_power_w": data.get("heater_power"),
            "calculation": "estimation",
            "note": "Pour une mesure précise, configurez un capteur de puissance",
        }


class DailyEnergySensor(HomePerformanceBaseSensor):
    """Sensor for daily energy consumption (rolling 24h window, estimated)."""

    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt-outline"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "daily_energy")
        self._attr_name = "Énergie 24h (estimée)"

    @property
    def native_value(self) -> float | None:
        """Return daily energy in kWh."""
        if self.coordinator.data:
            value = self.coordinator.data.get("daily_energy_kwh")
            if value is not None:
                return round(value, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "description": "Énergie estimée sur les dernières 24h glissantes",
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

    _attr_state_class = None  # Text format, no state class
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "heating_time")
        self._attr_name = "Temps de chauffe (24h)"

    @property
    def native_value(self) -> str | None:
        """Return heating time in human readable format."""
        if self.coordinator.data:
            value = self.coordinator.data.get("heating_hours")
            return format_duration(value)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        hours = data.get("heating_hours")
        # Source: power sensor (measured) or switch/climate state (estimated)
        has_power_sensor = self.coordinator.power_sensor is not None
        return {
            "hours_decimal": round(hours, 2) if hours is not None else None,
            "source": "measured" if has_power_sensor else "estimated",
            "detection": f"power > 50W ({self.coordinator.power_sensor})" if has_power_sensor else f"état {self.coordinator.heating_entity}",
            "description": "Temps cumulé de chauffe sur les dernières 24h",
        }


class HeatingRatioSensor(HomePerformanceBaseSensor):
    """Sensor for heating ratio (% of time heating is on)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:percent"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "heating_ratio")
        self._attr_name = "Ratio de chauffe"

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
        return {
            "description": "Pourcentage du temps où le chauffage est actif sur 24h",
            "source": "measured" if has_power_sensor else "estimated",
        }


class EnergyPerformanceSensor(HomePerformanceBaseSensor):
    """Sensor for energy performance evaluation based on French national statistics."""

    _attr_icon = "mdi:leaf"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "energy_performance")
        self._attr_name = "Performance énergétique"

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
            "excellent": "🟢 Excellente",
            "standard": "🟡 Standard",
            "to_optimize": "🟠 À optimiser",
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
                "Évaluation basée sur les statistiques nationales françaises. "
                "Seuils calculés selon la puissance du radiateur."
            ),
        }


class DeltaTSensor(HomePerformanceBaseSensor):
    """Sensor for average temperature difference."""

    _attr_native_unit_of_measurement = "°C"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "avg_delta_t")
        self._attr_name = "ΔT moyen (24h)"

    @property
    def native_value(self) -> float | None:
        """Return average ΔT."""
        if self.coordinator.data:
            value = self.coordinator.data.get("avg_delta_t")
            if value is not None:
                return round(value, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "description": "Écart moyen entre température intérieure et extérieure sur 24h",
            "current_delta_t": (
                round(data.get("delta_t"), 1)
                if data.get("delta_t") is not None
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
        }


class DataHoursSensor(HomePerformanceBaseSensor):
    """Sensor for hours of data collected."""

    _attr_state_class = None  # Text format, no state class
    _attr_icon = "mdi:database-clock"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "data_hours")
        self._attr_name = "Heures de données"

    @property
    def native_value(self) -> str | None:
        """Return hours of data in human readable format."""
        if self.coordinator.data:
            value = self.coordinator.data.get("data_hours")
            return format_duration(value)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        hours = data.get("data_hours")
        return {
            "hours_decimal": round(hours, 2) if hours is not None else None,
            "samples_count": data.get("samples_count"),
            "data_ready": data.get("data_ready"),
            "min_hours_required": 12,
        }


class AnalysisTimeRemainingSensor(HomePerformanceBaseSensor):
    """Sensor for remaining time before data is ready."""

    _attr_state_class = None  # Text format, no state class
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "analysis_remaining")
        self._attr_name = "Temps restant analyse"

    @property
    def native_value(self) -> str | None:
        """Return remaining time in human readable format."""
        data_hours = 0
        data_ready = False
        
        if self.coordinator.data:
            data_hours = self.coordinator.data.get("data_hours", 0) or 0
            data_ready = self.coordinator.data.get("data_ready", False)
        
        if data_ready:
            return "Prêt"
        
        remaining = max(0, 12 - data_hours)
        return format_duration(remaining)

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
            "remaining_hours": round(remaining, 2) if not data_ready else 0,
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

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "analysis_progress")
        self._attr_name = "Progression analyse"

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
            "description": "Progression de la collecte de données (0-100%)",
        }


class InsulationRatingSensor(HomePerformanceBaseSensor):
    """Sensor for insulation rating (qualitative)."""

    _attr_icon = "mdi:home-thermometer"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "insulation_rating")
        self._attr_name = "Note d'isolation"

    @property
    def native_value(self) -> str | None:
        """Return insulation rating."""
        if self.coordinator.data:
            return self.coordinator.data.get("insulation_rating")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        rating = data.get("insulation_rating")

        rating_descriptions = {
            "excellent": "Très bien isolé",
            "good": "Bien isolé",
            "average": "Isolation moyenne",
            "poor": "Mal isolé",
            "very_poor": "Très mal isolé / pont thermique",
        }

        return {
            "description": rating_descriptions.get(rating, "En attente de données"),
            "k_per_m3": (
                round(data.get("k_per_m3"), 2)
                if data.get("k_per_m3") is not None
                else None
            ),
            "note": "Basé sur K/m³ - nécessite le volume configuré",
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

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "measured_energy_daily")
        self._attr_name = "Énergie jour (mesurée)"

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
            "description": "Compteur d'énergie journalier",
            "source": "external" if uses_external else "integrated",
            "energy_sensor": self.coordinator.energy_sensor if uses_external else None,
            "power_sensor": self.coordinator.power_sensor if not uses_external else None,
            "current_power_w": data.get("measured_power_w") if not uses_external else None,
        }


class MeasuredEnergyTotalSensor(HomePerformanceBaseSensor):
    """Sensor for total measured energy - compatible with Energy Dashboard."""

    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "measured_energy_total")
        self._attr_name = "Énergie totale (mesurée)"

    @property
    def native_value(self) -> float | None:
        """Return total measured energy in kWh."""
        if self.coordinator.data:
            value = self.coordinator.data.get("measured_energy_total_kwh")
            if value is not None:
                return round(value, 3)
        return 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "description": "Énergie cumulée mesurée (compatible Dashboard Énergie)",
            "power_sensor": self.coordinator.power_sensor,
            "current_power_w": data.get("measured_power_w"),
            "calculation": "mesure_reelle",
            "note": "Utilisable dans Paramètres → Tableaux de bord → Énergie",
        }
