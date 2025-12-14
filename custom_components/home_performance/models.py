"""Thermal loss coefficient model for Home Performance.

This module implements a simple, physics-based approach to calculate
the thermal loss coefficient K (W/°C) of a room.

Formula: K = Energy / (ΔT × duration)

Where:
- Energy = heater_power × heating_time (in Wh)
- ΔT = average temperature difference (indoor - outdoor)
- duration = observation period (in hours)

Example: 1000W heater running 6h/24h to maintain 19°C when it's 5°C outside:
- Energy = 1000W × 6h = 6000 Wh
- ΔT = 14°C
- K = 6000 / (14 × 24) ≈ 18 W/°C

This room loses 18W per degree of temperature difference with outside.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from collections import deque
from typing import Any

from .const import (
    AGGREGATION_PERIOD_HOURS,
    MIN_DELTA_T,
    MIN_HEATING_TIME_HOURS,
    MIN_DATA_HOURS,
)

_LOGGER = logging.getLogger(__name__)

# Constants
SECONDS_PER_HOUR = 3600
MAX_DATA_POINTS = 1440 * 2  # 48h at 1 sample per minute


@dataclass
class ThermalDataPoint:
    """Single data point for thermal analysis."""

    timestamp: float  # Unix timestamp
    indoor_temp: float  # °C
    outdoor_temp: float  # °C
    heating_on: bool  # True if heater is running


@dataclass
class AggregatedPeriod:
    """Aggregated data over a period (typically 24h)."""

    start_time: float
    end_time: float
    heating_seconds: float  # Total seconds heating was on
    avg_indoor_temp: float
    avg_outdoor_temp: float
    sample_count: int

    @property
    def duration_hours(self) -> float:
        """Get period duration in hours."""
        return (self.end_time - self.start_time) / SECONDS_PER_HOUR

    @property
    def heating_hours(self) -> float:
        """Get heating time in hours."""
        return self.heating_seconds / SECONDS_PER_HOUR

    @property
    def delta_t(self) -> float:
        """Get average ΔT (indoor - outdoor)."""
        return self.avg_indoor_temp - self.avg_outdoor_temp

    @property
    def heating_ratio(self) -> float:
        """Get ratio of heating time vs total time (0-1)."""
        if self.duration_hours <= 0:
            return 0.0
        return self.heating_hours / self.duration_hours


class ThermalLossModel:
    """Model to calculate thermal loss coefficient K.

    K (W/°C) represents how much power (in Watts) is needed to maintain
    a 1°C temperature difference with the outside.

    Lower K = better insulation
    Higher K = more heat loss (worse insulation)

    Typical values:
    - Well insulated room: 10-20 W/°C
    - Average room: 20-40 W/°C
    - Poorly insulated room: 40-80 W/°C
    """

    def __init__(
        self,
        zone_name: str,
        heater_power: float,
        surface: float | None = None,
        volume: float | None = None,
    ) -> None:
        """Initialize the thermal loss model.

        Args:
            zone_name: Name of the zone/room
            heater_power: Declared power of the heater in Watts
            surface: Room surface in m² (optional, for K/m²)
            volume: Room volume in m³ (optional, for K/m³)
        """
        self.zone_name = zone_name
        self.heater_power = heater_power  # W
        self.surface = surface  # m²
        self.volume = volume  # m³

        # Data storage
        self.data_points: deque[ThermalDataPoint] = deque(maxlen=MAX_DATA_POINTS)

        # Calculated values (updated periodically)
        self._k_coefficient: float | None = None  # W/°C
        self._last_aggregation: AggregatedPeriod | None = None

        # Tracking
        self._last_point: ThermalDataPoint | None = None

    @property
    def samples_count(self) -> int:
        """Get total number of data points."""
        return len(self.data_points)

    @property
    def data_hours(self) -> float:
        """Get hours of data collected."""
        if len(self.data_points) < 2:
            return 0.0
        return (
            self.data_points[-1].timestamp - self.data_points[0].timestamp
        ) / SECONDS_PER_HOUR

    @property
    def k_coefficient(self) -> float | None:
        """Get thermal loss coefficient K in W/°C."""
        return self._k_coefficient

    @property
    def k_per_m2(self) -> float | None:
        """Get K normalized by surface (W/(°C·m²))."""
        if self._k_coefficient is None or self.surface is None:
            return None
        return self._k_coefficient / self.surface

    @property
    def k_per_m3(self) -> float | None:
        """Get K normalized by volume (W/(°C·m³))."""
        if self._k_coefficient is None or self.volume is None:
            return None
        return self._k_coefficient / self.volume

    def add_data_point(self, point: ThermalDataPoint) -> None:
        """Add a new data point and update calculations."""
        self.data_points.append(point)
        self._last_point = point

        # Recalculate K if we have enough data
        if self.data_hours >= MIN_DATA_HOURS:
            self._calculate_k()

    def _calculate_k(self) -> None:
        """Calculate K from aggregated data over the last AGGREGATION_PERIOD_HOURS."""
        if len(self.data_points) < 2:
            return

        now = self.data_points[-1].timestamp
        period_start = now - (AGGREGATION_PERIOD_HOURS * SECONDS_PER_HOUR)

        # Get points in the aggregation period
        period_points = [p for p in self.data_points if p.timestamp >= period_start]

        if len(period_points) < 10:  # Need minimum points
            _LOGGER.debug(
                "Not enough points for K calculation: %d", len(period_points)
            )
            return

        # Calculate aggregated values
        aggregation = self._aggregate_period(period_points)
        self._last_aggregation = aggregation

        # Check minimum conditions
        if aggregation.delta_t < MIN_DELTA_T:
            _LOGGER.debug(
                "ΔT too low for reliable K calculation: %.1f°C (min: %.1f°C)",
                aggregation.delta_t,
                MIN_DELTA_T,
            )
            return

        if aggregation.heating_hours < MIN_HEATING_TIME_HOURS:
            _LOGGER.debug(
                "Heating time too low: %.2fh (min: %.1fh)",
                aggregation.heating_hours,
                MIN_HEATING_TIME_HOURS,
            )
            return

        # Calculate K
        # Energy = Power × heating_time (Wh)
        energy_wh = self.heater_power * aggregation.heating_hours

        # K = Energy / (ΔT × duration)
        k = energy_wh / (aggregation.delta_t * aggregation.duration_hours)

        self._k_coefficient = k

        _LOGGER.info(
            "K calculated for %s: %.1f W/°C "
            "(energy=%.0f Wh, ΔT=%.1f°C, duration=%.1fh, heating=%.1fh)",
            self.zone_name,
            k,
            energy_wh,
            aggregation.delta_t,
            aggregation.duration_hours,
            aggregation.heating_hours,
        )

    def _aggregate_period(self, points: list[ThermalDataPoint]) -> AggregatedPeriod:
        """Aggregate data points over a period."""
        if not points:
            raise ValueError("No points to aggregate")

        # Sort by timestamp
        points = sorted(points, key=lambda p: p.timestamp)

        start_time = points[0].timestamp
        end_time = points[-1].timestamp

        # Calculate heating time by summing intervals where heating was on
        heating_seconds = 0.0
        for i in range(1, len(points)):
            if points[i - 1].heating_on:
                interval = points[i].timestamp - points[i - 1].timestamp
                heating_seconds += interval

        # Calculate average temperatures
        avg_indoor = sum(p.indoor_temp for p in points) / len(points)
        avg_outdoor = sum(p.outdoor_temp for p in points) / len(points)

        return AggregatedPeriod(
            start_time=start_time,
            end_time=end_time,
            heating_seconds=heating_seconds,
            avg_indoor_temp=avg_indoor,
            avg_outdoor_temp=avg_outdoor,
            sample_count=len(points),
        )

    def get_analysis(self) -> dict[str, Any]:
        """Get current analysis results."""
        agg = self._last_aggregation

        return {
            # Main coefficient
            "k_coefficient": self._k_coefficient,
            "k_per_m2": self.k_per_m2,
            "k_per_m3": self.k_per_m3,
            # Aggregation data
            "heating_hours": agg.heating_hours if agg else None,
            "heating_ratio": agg.heating_ratio if agg else None,
            "avg_delta_t": agg.delta_t if agg else None,
            "daily_energy_kwh": (
                (self.heater_power * agg.heating_hours / 1000) if agg else None
            ),
            # Status
            "data_hours": self.data_hours,
            "samples_count": self.samples_count,
            "data_ready": self.data_hours >= MIN_DATA_HOURS,
            # Configuration
            "heater_power": self.heater_power,
            "surface": self.surface,
            "volume": self.volume,
        }

    def get_insulation_rating(self) -> str | None:
        """Get a human-readable insulation rating based on K/m³.

        Using K/m³ as it's more comparable across different room sizes.
        """
        k_m3 = self.k_per_m3
        if k_m3 is None:
            return None

        # Thresholds based on typical values
        # These are approximate and may need adjustment
        if k_m3 < 0.4:
            return "excellent"  # Very well insulated
        elif k_m3 < 0.7:
            return "good"  # Well insulated
        elif k_m3 < 1.0:
            return "average"  # Average insulation
        elif k_m3 < 1.5:
            return "poor"  # Poor insulation
        else:
            return "very_poor"  # Very poor insulation / thermal bridge
