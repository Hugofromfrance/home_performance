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
from homeassistant.util import slugify

from .const import BINARY_SENSOR_ENTITY_SUFFIXES, DOMAIN, MIN_DATA_HOURS, VERSION
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
        HeatingActiveSensor(coordinator, zone_name),
        DataReadySensor(coordinator, zone_name),
    ]

    async_add_entities(entities)


class HomePerformanceBaseBinarySensor(CoordinatorEntity[HomePerformanceCoordinator], BinarySensorEntity):
    """Base class for Home Performance binary sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomePerformanceCoordinator,
        zone_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the binary sensor."""
        self._zone_name = zone_name
        self._sensor_type = sensor_type
        # Use slugify for consistent handling of special characters (ü, é, ç, etc.)
        zone_slug = slugify(zone_name, separator="_")
        
        # Set unique_id and suggested_object_id BEFORE super().__init__()
        # to ensure they are available when the entity is registered
        self._attr_unique_id = f"home_performance_{zone_slug}_{sensor_type}"
        
        # Suggest standardized entity_id for new installations
        # Existing users keep their current entity_id via Entity Registry
        suffix = BINARY_SENSOR_ENTITY_SUFFIXES.get(sensor_type, sensor_type)
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


class WindowOpenSensor(HomePerformanceBaseBinarySensor):
    """Binary sensor for window open detection."""

    _attr_device_class = BinarySensorDeviceClass.WINDOW
    _attr_icon = "mdi:window-open-variant"
    _attr_name = "Window open"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "window_open")

    @property
    def is_on(self) -> bool:
        """Return true if window is detected as open."""
        if self.coordinator.data:
            return self.coordinator.data.get("window_open", False)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        # Get detection method from coordinator data
        detection_method = "temperature"
        if self.coordinator.data:
            detection_method = self.coordinator.data.get("window_detection_method", "temperature")

        if detection_method == "sensor":
            return {
                "detection_method": "sensor",
                "sensor_entity": self.coordinator.window_sensor,
                "description": "Using physical window/door contact sensor",
            }
        else:
            return {
                "detection_method": "temperature",
                "description": "Detected via rapid temperature drop",
            }


class HeatingActiveSensor(HomePerformanceBaseBinarySensor):
    """Binary sensor for heating active state."""

    _attr_device_class = BinarySensorDeviceClass.HEAT
    _attr_icon = "mdi:fire"
    _attr_name = "Heating active"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "heating_active")

    @property
    def is_on(self) -> bool:
        """Return true if heating is currently active."""
        if self.coordinator.data:
            return self.coordinator.data.get("heating_on", False)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.data:
            return {
                "heating_hours_today": round(self.coordinator.data.get("heating_hours", 0), 2),
                "heating_ratio": round(self.coordinator.data.get("heating_ratio", 0) * 100, 1),
                "description": "Heating is currently running",
            }
        return {
            "heating_hours_today": 0,
            "heating_ratio": 0,
            "description": "Heating state unknown",
        }


class DataReadySensor(HomePerformanceBaseBinarySensor):
    """Binary sensor indicating if enough data has been collected."""

    _attr_icon = "mdi:database-check"
    _attr_name = "Data ready"

    def __init__(self, coordinator: HomePerformanceCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "data_ready")

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
                "description": f"Requires at least {MIN_DATA_HOURS}h of data",
            }
        # Storage not yet loaded - return loading state
        return {
            "data_hours": 0,
            "min_hours_required": MIN_DATA_HOURS,
            "samples_count": 0,
            "storage_loaded": False,
            "description": "Loading data...",
        }
