"""Sensor platform for Thermal Learning."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime, UnitOfPower, UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ZONE_NAME, CONF_POWER_SENSOR, CONF_VOLUME
from .coordinator import ThermalLearningCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Thermal Learning sensors."""
    coordinator: ThermalLearningCoordinator = hass.data[DOMAIN][entry.entry_id]
    zone_name = entry.data[CONF_ZONE_NAME]

    entities = [
        ThermalInertiaSensor(coordinator, zone_name),
        CoolingRateSensor(coordinator, zone_name),
        TimeToTargetSensor(coordinator, zone_name),
        LearningProgressSensor(coordinator, zone_name),
        ConfidenceSensor(coordinator, zone_name),
        HeatingCyclesSensor(coordinator, zone_name),
        CoolingCyclesSensor(coordinator, zone_name),
    ]

    # Only add Thermal Loss Coefficient sensor if it can be calculated
    # (requires power_sensor OR volume to be configured)
    if coordinator.can_calculate_thermal_loss():
        entities.append(ThermalLossCoefficientSensor(coordinator, zone_name))
        _LOGGER.debug(
            "Thermal Loss Coefficient sensor enabled (power_sensor=%s, volume=%s)",
            coordinator.power_sensor is not None,
            coordinator.volume is not None,
        )
    else:
        _LOGGER.info(
            "Thermal Loss Coefficient sensor disabled: configure power_sensor or volume to enable"
        )

    async_add_entities(entities)


class ThermalLearningBaseSensor(CoordinatorEntity[ThermalLearningCoordinator], SensorEntity):
    """Base class for Thermal Learning sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThermalLearningCoordinator,
        zone_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
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


class ThermalLossCoefficientSensor(ThermalLearningBaseSensor):
    """Sensor for thermal loss coefficient (G)."""

    _attr_native_unit_of_measurement = "W/°C"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:heat-wave"

    def __init__(self, coordinator: ThermalLearningCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "thermal_loss_coefficient")
        self._attr_name = "Thermal Loss Coefficient"

    @property
    def native_value(self) -> float | None:
        """Return the thermal loss coefficient."""
        if self.coordinator.data:
            value = self.coordinator.data.get("thermal_loss_coefficient")
            if value is not None:
                return round(value, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        from_power = self.coordinator.data.get("thermal_loss_from_power") if self.coordinator.data else None
        calculation_method = None
        if from_power is True:
            calculation_method = "power_sensor"
        elif from_power is False:
            calculation_method = "volume_estimation"
        
        return {
            "description": "Heat loss per degree of temperature difference (W/°C)",
            "calculation_method": calculation_method,
            "confidence": self.coordinator.data.get("confidence") if self.coordinator.data else None,
            "volume_m3": self.coordinator.volume,
            "power_sensor": self.coordinator.power_sensor,
        }


class ThermalInertiaSensor(ThermalLearningBaseSensor):
    """Sensor for thermal inertia (time constant)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator: ThermalLearningCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "thermal_inertia")
        self._attr_name = "Thermal Inertia"

    def _get_raw_value_minutes(self) -> float | None:
        """Get raw value in minutes."""
        if self.coordinator.data:
            return self.coordinator.data.get("thermal_inertia")
        return None

    @property
    def native_value(self) -> float | None:
        """Return the thermal inertia with adaptive formatting."""
        value_min = self._get_raw_value_minutes()
        if value_min is None:
            return None

        # Convert to appropriate unit
        if value_min < 1:
            # Less than 1 minute -> show in seconds
            return round(value_min * 60, 0)
        elif value_min >= 60:
            # 60+ minutes -> show in hours
            return round(value_min / 60, 1)
        else:
            # 1-60 minutes -> show in minutes
            return round(value_min, 1)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement based on value."""
        value_min = self._get_raw_value_minutes()
        if value_min is None:
            return UnitOfTime.MINUTES

        if value_min < 1:
            return UnitOfTime.SECONDS
        elif value_min >= 60:
            return UnitOfTime.HOURS
        else:
            return UnitOfTime.MINUTES

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        raw_value = self._get_raw_value_minutes()
        return {
            "description": "Time to raise temperature by 1°C",
            "raw_value_minutes": round(raw_value, 2) if raw_value else None,
            "heating_cycles_analyzed": len(self.coordinator.thermal_model.heating_cycles),
        }


class CoolingRateSensor(ThermalLearningBaseSensor):
    """Sensor for cooling rate."""

    _attr_native_unit_of_measurement = "°C/h"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer-minus"

    def __init__(self, coordinator: ThermalLearningCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "cooling_rate")
        self._attr_name = "Cooling Rate"

    @property
    def native_value(self) -> float | None:
        """Return the cooling rate."""
        if self.coordinator.data:
            value = self.coordinator.data.get("cooling_rate")
            if value is not None:
                return round(value, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "description": "Temperature drop rate when heating is off (°C/h per 10°C ΔT)",
            "cooling_cycles_analyzed": len(self.coordinator.thermal_model.cooling_cycles),
        }


class TimeToTargetSensor(ThermalLearningBaseSensor):
    """Sensor for estimated time to reach target temperature."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_icon = "mdi:clock-fast"

    def __init__(self, coordinator: ThermalLearningCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "time_to_target")
        self._attr_name = "Time to Target"

    def _get_raw_value_minutes(self) -> float | None:
        """Get raw value in minutes."""
        target = self.coordinator.get_target_temperature()
        if target is None:
            return None
        return self.coordinator.thermal_model.get_time_to_target(target)

    @property
    def native_value(self) -> float | None:
        """Return the estimated time to target with adaptive formatting."""
        value_min = self._get_raw_value_minutes()
        if value_min is None:
            return None

        # Convert to appropriate unit
        if value_min < 1:
            # Less than 1 minute -> show in seconds
            return round(value_min * 60, 0)
        elif value_min >= 60:
            # 60+ minutes -> show in hours
            return round(value_min / 60, 1)
        else:
            # 1-60 minutes -> show in minutes
            return round(value_min, 0)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement based on value."""
        value_min = self._get_raw_value_minutes()
        if value_min is None:
            return UnitOfTime.MINUTES

        if value_min < 1:
            return UnitOfTime.SECONDS
        elif value_min >= 60:
            return UnitOfTime.HOURS
        else:
            return UnitOfTime.MINUTES

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        target = self.coordinator.get_target_temperature()
        current = self.coordinator.data.get("indoor_temp") if self.coordinator.data else None
        raw_value = self._get_raw_value_minutes()
        return {
            "target_temperature": target,
            "current_temperature": current,
            "raw_value_minutes": round(raw_value, 2) if raw_value else None,
            "description": "Estimated time to reach target temperature",
        }


class LearningProgressSensor(ThermalLearningBaseSensor):
    """Sensor for learning progress."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:school"

    def __init__(self, coordinator: ThermalLearningCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "learning_progress")
        self._attr_name = "Learning Progress"

    @property
    def native_value(self) -> float | None:
        """Return the learning progress."""
        if self.coordinator.data:
            return round(self.coordinator.data.get("learning_progress", 0), 0)
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "samples_count": self.coordinator.data.get("samples_count") if self.coordinator.data else 0,
            "learning_days": round(self.coordinator.thermal_model.learning_days, 1),
            "heating_cycles": len(self.coordinator.thermal_model.heating_cycles),
            "cooling_cycles": len(self.coordinator.thermal_model.cooling_cycles),
        }


class ConfidenceSensor(ThermalLearningBaseSensor):
    """Sensor for model confidence."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:check-circle"

    def __init__(self, coordinator: ThermalLearningCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "confidence")
        self._attr_name = "Model Confidence"

    @property
    def native_value(self) -> float | None:
        """Return the model confidence."""
        if self.coordinator.data:
            return round(self.coordinator.data.get("confidence", 0), 0)
        return 0


class HeatingCyclesSensor(ThermalLearningBaseSensor):
    """Sensor for counting heating cycles."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: ThermalLearningCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "heating_cycles")
        self._attr_name = "Heating Cycles"

    @property
    def native_value(self) -> int:
        """Return the number of heating cycles."""
        return len(self.coordinator.thermal_model.heating_cycles)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        cycles = self.coordinator.thermal_model.heating_cycles
        last_cycle = cycles[-1] if cycles else None
        return {
            "description": "Number of heating cycles detected",
            "required_for_calculation": 3,
            "last_cycle_duration_min": round(last_cycle.duration_minutes, 1) if last_cycle else None,
            "last_cycle_temp_rise": round(last_cycle.temp_rise, 2) if last_cycle else None,
        }


class CoolingCyclesSensor(ThermalLearningBaseSensor):
    """Sensor for counting cooling cycles."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator: ThermalLearningCoordinator, zone_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, zone_name, "cooling_cycles")
        self._attr_name = "Cooling Cycles"

    @property
    def native_value(self) -> int:
        """Return the number of cooling cycles."""
        return len(self.coordinator.thermal_model.cooling_cycles)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        cycles = self.coordinator.thermal_model.cooling_cycles
        last_cycle = cycles[-1] if cycles else None
        return {
            "description": "Number of cooling cycles detected",
            "required_for_calculation": 3,
            "last_cycle_duration_min": round(last_cycle.duration_minutes, 1) if last_cycle else None,
            "last_cycle_temp_drop": round(last_cycle.temp_drop, 2) if last_cycle else None,
            "last_cycle_cooling_rate": round(last_cycle.cooling_rate, 2) if last_cycle else None,
        }