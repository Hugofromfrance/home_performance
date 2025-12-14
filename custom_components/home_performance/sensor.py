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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Home Performance sensors."""
    coordinator: HomePerformanceCoordinator = hass.data[DOMAIN][entry.entry_id]
    zone_name = entry.data[CONF_ZONE_NAME]

    entities = [
        # Main coefficient
        ThermalLossCoefficientSensor(coordinator, zone_name),
        # Normalized coefficients (only if surface/volume configured)
        KPerM2Sensor(coordinator, zone_name),
        KPerM3Sensor(coordinator, zone_name),
        # Energy and usage
        DailyEnergySensor(coordinator, zone_name),
        HeatingTimeSensor(coordinator, zone_name),
        HeatingRatioSensor(coordinator, zone_name),
        # Temperature
        DeltaTSensor(coordinator, zone_name),
        # Status
        DataHoursSensor(coordinator, zone_name),
        InsulationRatingSensor(coordinator, zone_name),
    ]

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


class DailyEnergySensor(HomePerformanceBaseSensor):
    """Sensor for daily energy consumption."""

    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "daily_energy")
        self._attr_name = "Énergie journalière"

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
            "description": "Énergie consommée sur les dernières 24h",
            "heater_power_w": data.get("heater_power"),
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
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "heating_time")
        self._attr_name = "Temps de chauffe (24h)"

    @property
    def native_value(self) -> float | None:
        """Return heating time in hours."""
        if self.coordinator.data:
            value = self.coordinator.data.get("heating_hours")
            if value is not None:
                return round(value, 1)
        return None


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
        return {
            "description": "Pourcentage du temps où le chauffage est actif sur 24h",
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
        }


class DataHoursSensor(HomePerformanceBaseSensor):
    """Sensor for hours of data collected."""

    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:database-clock"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "data_hours")
        self._attr_name = "Heures de données"

    @property
    def native_value(self) -> float | None:
        """Return hours of data."""
        if self.coordinator.data:
            value = self.coordinator.data.get("data_hours")
            if value is not None:
                return round(value, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        return {
            "samples_count": data.get("samples_count"),
            "data_ready": data.get("data_ready"),
            "min_hours_required": 12,
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
