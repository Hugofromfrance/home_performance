"""Binary sensor platform for Home Performance."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ZONE_NAME, MIN_DATA_HOURS
from .coordinator import HomePerformanceCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Home Performance binary sensors."""
    coordinator: HomePerformanceCoordinator = hass.data[DOMAIN][entry.entry_id]
    zone_name = coordinator.zone_name

    entities = [
        WindowOpenSensor(coordinator, zone_name),
        DataReadySensor(coordinator, zone_name),
    ]

    async_add_entities(entities)


class HomePerformanceBaseBinarySensor(
    CoordinatorEntity[HomePerformanceCoordinator], BinarySensorEntity
):
    """Base class for Home Performance binary sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomePerformanceCoordinator,
        zone_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the binary sensor."""
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
            "sw_version": "1.1.1",
        }


class WindowOpenSensor(HomePerformanceBaseBinarySensor):
    """Binary sensor for window open detection."""

    _attr_device_class = BinarySensorDeviceClass.WINDOW
    _attr_icon = "mdi:window-open-variant"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "window_open")
        self._attr_name = "Fenêtre ouverte"

    @property
    def is_on(self) -> bool:
        """Return true if window is detected as open."""
        if self.coordinator.data:
            return self.coordinator.data.get("window_open", False)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "detection_method": "rapid_temperature_drop",
            "description": "Détecté via une chute rapide de température",
        }


class DataReadySensor(HomePerformanceBaseBinarySensor):
    """Binary sensor indicating if enough data has been collected."""

    _attr_icon = "mdi:database-check"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "data_ready")
        self._attr_name = "Données prêtes"

    @property
    def is_on(self) -> bool:
        """Return true if enough data has been collected."""
        if self.coordinator.data:
            return self.coordinator.data.get("data_ready", False)
        return False

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        if self.is_on:
            return "mdi:database-check"
        return "mdi:database-clock"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.data:
            data_hours = self.coordinator.data.get("data_hours", 0)
            storage_loaded = self.coordinator.data.get("storage_loaded", False)
            return {
                "data_hours": round(data_hours, 1) if data_hours else 0,
                "min_hours_required": MIN_DATA_HOURS,
                "samples_count": self.coordinator.data.get("samples_count", 0),
                "storage_loaded": storage_loaded,
                "description": f"Nécessite au moins {MIN_DATA_HOURS}h de données",
            }
        # Storage not yet loaded - return loading state
        return {
            "data_hours": 0,
            "min_hours_required": MIN_DATA_HOURS,
            "samples_count": 0,
            "storage_loaded": False,
            "description": "Chargement des données...",
        }
