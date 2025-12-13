"""Thermal models and learning algorithms for Thermal Learning."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from collections import deque
from typing import Any

from .const import (
    MIN_SAMPLES_FOR_CONFIDENCE,
    MIN_LEARNING_DAYS,
    MIN_HEATING_CYCLE_MINUTES,
    MIN_HEATING_CYCLE_TEMP_RISE,
    MIN_COOLING_CYCLE_MINUTES,
    MIN_COOLING_CYCLE_TEMP_DROP,
)

_LOGGER = logging.getLogger(__name__)

# Constants for calculations
SECONDS_PER_DAY = 86400
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60
MAX_DATA_POINTS = 10080  # 7 days at 1 sample per minute


@dataclass
class ThermalDataPoint:
    """Single data point for thermal analysis."""

    timestamp: float
    indoor_temp: float
    outdoor_temp: float
    heating_on: bool
    power: float | None = None


@dataclass
class HeatingCycle:
    """Represents a complete heating cycle for analysis."""

    start_time: float
    end_time: float
    start_temp: float
    end_temp: float
    outdoor_temp_avg: float
    power_avg: float | None = None

    @property
    def duration_minutes(self) -> float:
        """Get cycle duration in minutes."""
        return (self.end_time - self.start_time) / SECONDS_PER_MINUTE

    @property
    def temp_rise(self) -> float:
        """Get temperature rise during cycle."""
        return self.end_temp - self.start_temp


@dataclass
class CoolingCycle:
    """Represents a cooling period for analysis."""

    start_time: float
    end_time: float
    start_temp: float
    end_temp: float
    outdoor_temp_avg: float

    @property
    def duration_minutes(self) -> float:
        """Get cycle duration in minutes."""
        return (self.end_time - self.start_time) / SECONDS_PER_MINUTE

    @property
    def temp_drop(self) -> float:
        """Get temperature drop during cycle."""
        return self.start_temp - self.end_temp

    @property
    def cooling_rate(self) -> float:
        """Get cooling rate in °C per hour."""
        hours = (self.end_time - self.start_time) / SECONDS_PER_HOUR
        if hours <= 0:
            return 0.0
        return self.temp_drop / hours


class ThermalModel:
    """Thermal learning model for a zone."""

    # Typical effective thermal capacity per m³ (includes air, walls, furniture)
    # Value in Wh/(m³·°C) - typical range 30-50 for residential buildings
    THERMAL_CAPACITY_PER_M3 = 40.0

    def __init__(self, zone_name: str, volume: float | None = None) -> None:
        """Initialize the thermal model."""
        self.zone_name = zone_name
        self.volume = volume  # m³
        self.data_points: deque[ThermalDataPoint] = deque(maxlen=MAX_DATA_POINTS)
        self.heating_cycles: list[HeatingCycle] = []
        self.cooling_cycles: list[CoolingCycle] = []

        # Learned parameters
        self._thermal_loss_coefficient: float | None = None  # W/°C
        self._thermal_loss_from_power: bool = False  # True if calculated from power, False if estimated
        self._thermal_inertia: float | None = None  # minutes
        self._cooling_rate: float | None = None  # °C/hour

        # Tracking for cycle detection
        self._heating_start: ThermalDataPoint | None = None
        self._cooling_start: ThermalDataPoint | None = None
        self._was_heating: bool = False

    @property
    def samples_count(self) -> int:
        """Get total number of data points."""
        return len(self.data_points)

    @property
    def first_sample_time(self) -> float | None:
        """Get timestamp of first sample."""
        if self.data_points:
            return self.data_points[0].timestamp
        return None

    @property
    def learning_days(self) -> float:
        """Get number of days of learning data."""
        if not self.data_points:
            return 0.0
        time_span = self.data_points[-1].timestamp - self.data_points[0].timestamp
        return time_span / SECONDS_PER_DAY

    def add_data_point(self, point: ThermalDataPoint) -> None:
        """Add a new data point and update analysis."""
        self.data_points.append(point)
        self._detect_cycles(point)
        self._update_learned_parameters()

    def _detect_cycles(self, point: ThermalDataPoint) -> None:
        """Detect heating and cooling cycles."""
        # Detect heating cycle start
        if point.heating_on and not self._was_heating:
            self._heating_start = point
            # End any ongoing cooling cycle
            if self._cooling_start is not None:
                self._end_cooling_cycle(point)

        # Detect heating cycle end
        elif not point.heating_on and self._was_heating:
            if self._heating_start is not None:
                self._end_heating_cycle(point)
            # Start cooling cycle
            self._cooling_start = point

        self._was_heating = point.heating_on

    def _end_heating_cycle(self, end_point: ThermalDataPoint) -> None:
        """Complete a heating cycle."""
        if self._heating_start is None:
            return

        # Calculate average outdoor temp during cycle
        cycle_points = [
            p for p in self.data_points
            if self._heating_start.timestamp <= p.timestamp <= end_point.timestamp
        ]
        if not cycle_points:
            self._heating_start = None
            return

        outdoor_avg = sum(p.outdoor_temp for p in cycle_points) / len(cycle_points)
        power_avg = None
        power_points = [p.power for p in cycle_points if p.power is not None]
        if power_points:
            power_avg = sum(power_points) / len(power_points)

        cycle = HeatingCycle(
            start_time=self._heating_start.timestamp,
            end_time=end_point.timestamp,
            start_temp=self._heating_start.indoor_temp,
            end_temp=end_point.indoor_temp,
            outdoor_temp_avg=outdoor_avg,
            power_avg=power_avg,
        )

        # Only keep cycles with meaningful duration and temp change
        # Use small tolerance (0.01) for floating point comparison
        if (cycle.duration_minutes >= MIN_HEATING_CYCLE_MINUTES - 0.01 
            and cycle.temp_rise >= MIN_HEATING_CYCLE_TEMP_RISE - 0.01):
            self.heating_cycles.append(cycle)
            _LOGGER.debug(
                "Heating cycle detected: %.1f°C rise in %.1f min",
                cycle.temp_rise, cycle.duration_minutes
            )

        self._heating_start = None

    def _end_cooling_cycle(self, end_point: ThermalDataPoint) -> None:
        """Complete a cooling cycle."""
        if self._cooling_start is None:
            return

        # Calculate average outdoor temp during cycle
        cycle_points = [
            p for p in self.data_points
            if self._cooling_start.timestamp <= p.timestamp <= end_point.timestamp
        ]
        if not cycle_points:
            self._cooling_start = None
            return

        outdoor_avg = sum(p.outdoor_temp for p in cycle_points) / len(cycle_points)

        cycle = CoolingCycle(
            start_time=self._cooling_start.timestamp,
            end_time=end_point.timestamp,
            start_temp=self._cooling_start.indoor_temp,
            end_temp=end_point.indoor_temp,
            outdoor_temp_avg=outdoor_avg,
        )

        # Only keep cycles with meaningful duration and temp drop
        # Use small tolerance (0.01) for floating point comparison
        if (cycle.duration_minutes >= MIN_COOLING_CYCLE_MINUTES - 0.01 
            and cycle.temp_drop >= MIN_COOLING_CYCLE_TEMP_DROP - 0.01):
            self.cooling_cycles.append(cycle)
            _LOGGER.debug(
                "Cooling cycle detected: %.1f°C drop in %.1f min (%.2f°C/h)",
                cycle.temp_drop, cycle.duration_minutes, cycle.cooling_rate
            )
        else:
            _LOGGER.debug(
                "Cooling cycle rejected: %.1f°C drop in %.1f min (need %.1f min and %.1f°C drop)",
                cycle.temp_drop, cycle.duration_minutes,
                MIN_COOLING_CYCLE_MINUTES, MIN_COOLING_CYCLE_TEMP_DROP
            )

        self._cooling_start = None

    def _update_learned_parameters(self) -> None:
        """Update learned thermal parameters based on collected cycles."""
        # Update thermal inertia from heating cycles
        if len(self.heating_cycles) >= 3:
            self._calculate_thermal_inertia()
            _LOGGER.debug(
                "Updated thermal_inertia=%.2f min (from %d heating cycles)",
                self._thermal_inertia or 0, len(self.heating_cycles)
            )

        # Update cooling rate from cooling cycles
        if len(self.cooling_cycles) >= 3:
            self._calculate_cooling_rate()

        # Update thermal loss coefficient
        if self._cooling_rate is not None and len(self.cooling_cycles) >= 3:
            self._calculate_thermal_loss()

    def _calculate_thermal_inertia(self) -> None:
        """Calculate thermal inertia (time constant) from heating cycles."""
        # Use recent cycles for calculation
        recent_cycles = self.heating_cycles[-10:]

        # Thermal inertia = average time to rise 1°C
        inertia_values = []
        for cycle in recent_cycles:
            if cycle.temp_rise > 0:
                minutes_per_degree = cycle.duration_minutes / cycle.temp_rise
                inertia_values.append(minutes_per_degree)

        if inertia_values:
            self._thermal_inertia = sum(inertia_values) / len(inertia_values)

    def _calculate_cooling_rate(self) -> None:
        """Calculate average cooling rate from cooling cycles."""
        recent_cycles = self.cooling_cycles[-10:]

        # Weight by delta T (indoor - outdoor) for normalization
        weighted_rates = []
        for cycle in recent_cycles:
            delta_t = (cycle.start_temp + cycle.end_temp) / 2 - cycle.outdoor_temp_avg
            if delta_t > 1:  # Minimum 1°C difference for meaningful data
                # Normalize to rate per 10°C delta
                normalized_rate = cycle.cooling_rate / delta_t * 10
                weighted_rates.append(normalized_rate)

        if weighted_rates:
            self._cooling_rate = sum(weighted_rates) / len(weighted_rates)

    def _calculate_thermal_loss(self) -> None:
        """Calculate thermal loss coefficient (G) in W/°C.
        
        Method 1 (preferred): From power data - G = P / ΔT
        Method 2 (fallback): From volume and cooling rate - G = C × cooling_rate / 10
        """
        # Try Method 1: Calculate from power data (most accurate)
        recent_cycles = self.heating_cycles[-10:]
        cycles_with_power = [c for c in recent_cycles if c.power_avg is not None]

        if cycles_with_power:
            g_values = []
            for cycle in cycles_with_power:
                delta_t = cycle.end_temp - cycle.outdoor_temp_avg
                if delta_t > 1 and cycle.power_avg and cycle.power_avg > 0:
                    g = cycle.power_avg / delta_t
                    g_values.append(g)

            if g_values:
                self._thermal_loss_coefficient = sum(g_values) / len(g_values)
                self._thermal_loss_from_power = True
                return

        # Try Method 2: Estimate from volume and cooling rate
        if self.volume is not None and self._cooling_rate is not None:
            # Thermal capacity: C = THERMAL_CAPACITY_PER_M3 × Volume (Wh/°C)
            # cooling_rate is normalized to ΔT=10°C
            # G = C × cooling_rate / 10 (W/°C)
            thermal_capacity = self.THERMAL_CAPACITY_PER_M3 * self.volume
            self._thermal_loss_coefficient = thermal_capacity * self._cooling_rate / 10.0
            self._thermal_loss_from_power = False
            _LOGGER.debug(
                "Thermal loss coefficient estimated from volume: %.1f W/°C (volume=%.1f m³, cooling_rate=%.2f °C/h)",
                self._thermal_loss_coefficient, self.volume, self._cooling_rate
            )

    def get_time_to_target(self, target_temp: float) -> float | None:
        """Estimate time in minutes to reach target temperature."""
        if not self.data_points or self._thermal_inertia is None:
            return None

        current_temp = self.data_points[-1].indoor_temp
        temp_diff = target_temp - current_temp

        if temp_diff <= 0:
            return 0.0  # Already at or above target

        # Simple linear estimation based on thermal inertia
        return temp_diff * self._thermal_inertia

    def get_current_analysis(self) -> dict[str, Any]:
        """Get current thermal analysis results."""
        # Calculate confidence based on data quantity and quality
        confidence = self._calculate_confidence()

        # Learning progress (0-100%)
        progress = min(100, (self.learning_days / MIN_LEARNING_DAYS) * 100)

        # Get target temperature if available
        target_temp = None
        time_to_target = None

        result = {
            "thermal_loss_coefficient": self._thermal_loss_coefficient,
            "thermal_loss_from_power": self._thermal_loss_from_power,
            "thermal_inertia": self._thermal_inertia,
            "cooling_rate": self._cooling_rate,
            "time_to_target": time_to_target,
            "learning_progress": progress,
            "learning_complete": progress >= 100 and confidence >= 50,
            "confidence": confidence,
            "heating_cycles_count": len(self.heating_cycles),
            "cooling_cycles_count": len(self.cooling_cycles),
        }

        _LOGGER.debug(
            "Analysis: inertia=%.2f, loss=%.1f, cooling_rate=%.2f, cycles(heat=%d, cool=%d)",
            self._thermal_inertia or 0,
            self._thermal_loss_coefficient or 0,
            self._cooling_rate or 0,
            len(self.heating_cycles),
            len(self.cooling_cycles),
        )

        return result

    def _calculate_confidence(self) -> float:
        """Calculate confidence level (0-100) in learned parameters."""
        confidence = 0.0

        # Factor 1: Number of samples (max 30 points)
        sample_factor = min(30, (self.samples_count / MIN_SAMPLES_FOR_CONFIDENCE) * 30)
        confidence += sample_factor

        # Factor 2: Number of heating cycles (max 30 points)
        heating_factor = min(30, len(self.heating_cycles) * 6)
        confidence += heating_factor

        # Factor 3: Number of cooling cycles (max 20 points)
        cooling_factor = min(20, len(self.cooling_cycles) * 4)
        confidence += cooling_factor

        # Factor 4: Learning duration (max 20 points)
        duration_factor = min(20, (self.learning_days / MIN_LEARNING_DAYS) * 20)
        confidence += duration_factor

        return min(100, confidence)