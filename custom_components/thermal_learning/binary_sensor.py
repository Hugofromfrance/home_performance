"""Binary sensor platform for Thermal Learning."""
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

from .const import DOMAIN, CONF_ZONE_NAME
from .coordinator import ThermalLearningCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Thermal Learning binary sensors."""
    coordinator: ThermalLearningCoordinator = hass.data[DOMAIN][entry.entry_id]
    zone_name = entry.data[CONF_ZONE_NAME]

    entities = [
        WindowOpenSensor(coordinator, zone_name),
        LearningCompleteSensor(coordinator, zone_name),
    ]

    async_add_entities(entities)


class ThermalLearningBaseBinarySensor(
    CoordinatorEntity[ThermalLearningCoordinator], BinarySensorEntity
):
    """Base class for Thermal Learning binary sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThermalLearningCoordinator,
        zone_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._zone_name = zone_name
        self._sensor_type = sensor_type
        self._attr_unique_id = f"thermal_learning_{zone_name}_{sensor_type}".lower().replace(" ", "_")

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._zone_name)},
            "name": f"Thermal Learning - {self._zone_name}",
            "manufacturer": "Thermal Learning",
            "model": "Thermal Analyzer",
            "sw_version": "0.1.0",
        }


class WindowOpenSensor(ThermalLearningBaseBinarySensor):
    """Binary sensor for window open detection."""

    _attr_device_class = BinarySensorDeviceClass.WINDOW
    _attr_icon = "mdi:window-open-variant"

    def __init__(self, coordinator: ThermalLearningCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "window_open")
        self._attr_name = "Window Open Detected"

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
            "description": "Detected via rapid temperature drop analysis",
        }


class LearningCompleteSensor(ThermalLearningBaseBinarySensor):
    """Binary sensor for learning completion status."""

    _attr_icon = "mdi:school-outline"

    def __init__(self, coordinator: ThermalLearningCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "learning_complete")
        self._attr_name = "Learning Complete"

    @property
    def is_on(self) -> bool:
        """Return true if learning is complete."""
        if self.coordinator.data:
            return self.coordinator.data.get("learning_complete", False)
        return False

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        if self.is_on:
            return "mdi:school"
        return "mdi:school-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.data:
            return {
                "learning_progress": self.coordinator.data.get("learning_progress", 0),
                "confidence": self.coordinator.data.get("confidence", 0),
                "samples_count": self.coordinator.data.get("samples_count", 0),
                "min_days_required": 7,
                "min_confidence_required": 50,
            }
        return {}