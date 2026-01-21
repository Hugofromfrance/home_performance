"""Thermal loss coefficient model for Home Performance.

This module implements a simple, physics-based approach to calculate
the thermal loss coefficient K (W/°C) of a room.

Formula: K = Energy / (ΔT × duration)

Where:
- Energy = measured or estimated heating energy consumption (in Wh)
- ΔT = average temperature difference (indoor - outdoor)
- duration = observation period (in hours)

Energy sources (in order of accuracy):
1. energy_sensor: External energy meter reading (most accurate)
2. power_sensor: Integrated power over time (accurate)
3. heater_power × heating_time: Estimated from declared power (fallback)

Example: Heater consuming 6kWh over 24h to maintain 19°C when it's 5°C outside:
- Energy = 6000 Wh (measured or estimated)
- ΔT = 14°C
- K = 6000 / (14 × 24) ≈ 18 W/°C

This room loses 18W per degree of temperature difference with outside.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any

from .const import (
    AGGREGATION_PERIOD_HOURS,
    HISTORY_DAYS,
    LONG_TERM_HISTORY_DAYS,
    MIN_DATA_HOURS,
    MIN_DELTA_T,
    MIN_HEATING_TIME_HOURS,
)

_LOGGER = logging.getLogger(__name__)

# Constants
SECONDS_PER_HOUR = 3600
MAX_DATA_POINTS = 1440 * 2  # 48h at 1 sample per minute

# Season/inference constants
TEMP_STABILITY_THRESHOLD = 3.0  # °C - max variation for "stable" temperature (increased for fast-cycling systems)
EXCELLENT_INFERENCE_MIN_HOURS = 24  # Hours needed to infer excellent isolation
MIN_COMFORT_TEMP = 17.0  # °C - minimum indoor temp to consider a "perfect" day (room must be comfortable)

# Season status codes
SEASON_SUMMER = "summer"  # T° ext > T° int (ΔT negative)
SEASON_OFF = "off_season"  # 0 < ΔT < MIN_DELTA_T
SEASON_HEATING = "heating_season"  # ΔT >= MIN_DELTA_T

# Insulation status codes
INSULATION_WAITING_DATA = "waiting_data"
INSULATION_WAITING_HEAT = "waiting_heat"
INSULATION_EXCELLENT_INFERRED = "excellent_inferred"
INSULATION_CALCULATED = "calculated"


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


@dataclass
class DailyHistoryEntry:
    """Daily aggregated data for 7-day rolling K calculation.

    Stores summary of one complete day of heating data.
    Used to calculate a stable K coefficient over multiple days.
    """

    date: str  # ISO format YYYY-MM-DD
    heating_hours: float  # Total heating hours that day
    avg_delta_t: float  # Average ΔT that day
    energy_kwh: float  # Estimated energy consumption
    avg_indoor_temp: float  # Average indoor temperature
    avg_outdoor_temp: float  # Average outdoor temperature
    sample_count: int  # Number of samples (data points)
    k_7d: float | None = None  # K_7j at the time of archival (for historical graph)
    # Temperature stability (for "excellent isolation" inference)
    temp_variation: float | None = None  # Indoor temp variation (max - min) in °C
    # Weather data (for future analysis)
    avg_wind_speed: float | None = None  # Average wind speed that day (km/h)
    dominant_wind_direction: str | None = None  # Most frequent wind direction
    # Dynamic COP for heat pumps (measured that day)
    measured_cop: float | None = None  # COP calculated from actual measurements

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for persistence."""
        result = {
            "date": self.date,
            "heating_hours": self.heating_hours,
            "avg_delta_t": self.avg_delta_t,
            "energy_kwh": self.energy_kwh,
            "avg_indoor_temp": self.avg_indoor_temp,
            "avg_outdoor_temp": self.avg_outdoor_temp,
            "sample_count": self.sample_count,
        }
        if self.k_7d is not None:
            result["k_7d"] = self.k_7d
        if self.temp_variation is not None:
            result["temp_variation"] = self.temp_variation
        if self.avg_wind_speed is not None:
            result["avg_wind_speed"] = self.avg_wind_speed
        if self.dominant_wind_direction is not None:
            result["dominant_wind_direction"] = self.dominant_wind_direction
        if self.measured_cop is not None:
            result["measured_cop"] = self.measured_cop
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DailyHistoryEntry:
        """Create from dictionary."""
        return cls(
            date=data["date"],
            heating_hours=data.get("heating_hours", 0.0),
            avg_delta_t=data.get("avg_delta_t", 0.0),
            energy_kwh=data.get("energy_kwh", 0.0),
            avg_indoor_temp=data.get("avg_indoor_temp", 0.0),
            avg_outdoor_temp=data.get("avg_outdoor_temp", 0.0),
            sample_count=data.get("sample_count", 0),
            k_7d=data.get("k_7d"),
            temp_variation=data.get("temp_variation"),
            avg_wind_speed=data.get("avg_wind_speed"),
            dominant_wind_direction=data.get("dominant_wind_direction"),
            measured_cop=data.get("measured_cop"),
        )


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

    Energy source hierarchy (most accurate first):
    1. energy_sensor: External energy meter (kWh) - direct measurement, most accurate
    2. power_sensor: Real-time power (W) integrated over time - calculated, accurate
    3. heater_power: Declared power (W) × heating time - estimation, least accurate

    Using measured energy (from energy_sensor or power_sensor) instead of declared
    heater_power provides more accurate K calculations because:
    - Actual efficiency losses are accounted for
    - Variable output (thermostatic radiators, modulating systems) is captured
    - Real consumption is measured, not estimated
    """

    def __init__(
        self,
        zone_name: str,
        heater_power: float | None = None,
        surface: float | None = None,
        volume: float | None = None,
        efficiency_factor: float = 1.0,
    ) -> None:
        """Initialize the thermal loss model.

        Args:
            zone_name: Name of the zone/room
            heater_power: Declared power of the heater in Watts (optional for energy-based sources)
            surface: Room surface in m² (optional, for K/m²)
            volume: Room volume in m³ (optional, for K/m³)
            efficiency_factor: Multiplier for energy conversion (1.0 for electric, ~3.0 for heat pump, ~0.85 for gas)
        """
        self.zone_name = zone_name
        self.heater_power = heater_power  # W - can be None for energy-based sources
        self.surface = surface  # m²
        self.volume = volume  # m³
        self.efficiency_factor = efficiency_factor  # Multiplier: consumed energy → heat output

        # Data storage
        self.data_points: deque[ThermalDataPoint] = deque(maxlen=MAX_DATA_POINTS)

        # Daily history for 7-day rolling K calculation (stable rating)
        self._daily_history: list[DailyHistoryEntry] = []

        # Calculated values (updated periodically)
        self._k_coefficient: float | None = None  # W/°C - current K from rolling 24h
        self._k_coefficient_7d: float | None = None  # W/°C - stable K from 7-day history
        self._last_valid_k: float | None = None  # Last valid K (preserved during off-season)
        self._last_k_date: str | None = None  # Date of last valid K calculation (ISO format)
        self._last_aggregation: AggregatedPeriod | None = None

        # Energy tracking (cumulative)
        self._total_energy_kwh: float = 0.0  # Cumulative energy in kWh
        self._measured_energy_kwh: float = 0.0  # Energy from external sensor (for energy-based sources)
        self._total_heating_hours: float = 0.0  # Total heating hours (for derived power calculation)

        # Tracking
        self._last_point: ThermalDataPoint | None = None

    @property
    def derived_power(self) -> float | None:
        """Calculate average power from measured energy and heating time.

        Used for performance thresholds when heater_power is not available.
        Returns power in Watts.
        """
        if self._total_heating_hours > 0 and self._measured_energy_kwh > 0:
            # Power (W) = Energy (kWh) / Time (h) * 1000
            return (self._measured_energy_kwh / self._total_heating_hours) * 1000
        return None

    @property
    def effective_power(self) -> float | None:
        """Get the power to use for calculations.

        Returns heater_power if available, otherwise derived_power.
        """
        if self.heater_power is not None and self.heater_power > 0:
            return self.heater_power
        return self.derived_power

    @property
    def samples_count(self) -> int:
        """Get total number of data points."""
        return len(self.data_points)

    @property
    def data_hours(self) -> float:
        """Get hours of data collected."""
        if len(self.data_points) < 2:
            return 0.0
        return (self.data_points[-1].timestamp - self.data_points[0].timestamp) / SECONDS_PER_HOUR

    @property
    def k_coefficient(self) -> float | None:
        """Get thermal loss coefficient K in W/°C.

        Returns the 7-day stable K if available, otherwise the 24h rolling K.
        This ensures the insulation rating is stable across midnight resets.
        """
        # Prefer 7-day stable K for rating consistency
        if self._k_coefficient_7d is not None:
            return self._k_coefficient_7d
        return self._k_coefficient

    @property
    def k_coefficient_24h(self) -> float | None:
        """Get the 24-hour rolling K coefficient (real-time)."""
        return self._k_coefficient

    @property
    def k_coefficient_7d(self) -> float | None:
        """Get the 7-day stable K coefficient."""
        return self._k_coefficient_7d

    @property
    def daily_history(self) -> list[DailyHistoryEntry]:
        """Get the daily history entries."""
        return self._daily_history.copy()

    @property
    def history_days_count(self) -> int:
        """Get number of days in history."""
        return len(self._daily_history)

    @property
    def k_per_m2(self) -> float | None:
        """Get K normalized by surface (W/(°C·m²)).

        Uses stable K (prefers 7-day average) for consistent comparisons.
        """
        if self.k_coefficient is None or self.surface is None:
            return None
        return self.k_coefficient / self.surface

    @property
    def k_per_m3(self) -> float | None:
        """Get K normalized by volume (W/(°C·m³)).

        Uses stable K (prefers 7-day average) for consistent comparisons.
        """
        if self.k_coefficient is None or self.volume is None:
            return None
        return self.k_coefficient / self.volume

    @property
    def cop_7d(self) -> float | None:
        """Get the 7-day average COP for heat pumps.

        Calculates the average of measured_cop values from the last 7 days
        of daily history. Only includes days where COP was successfully measured.

        Returns:
            Average COP over 7 days, or None if not enough data.
        """
        if not self._daily_history:
            return None

        # Get COP values from last 7 days (most recent entries)
        recent_entries = self._daily_history[-HISTORY_DAYS:]
        cop_values = [
            entry.measured_cop for entry in recent_entries if entry.measured_cop is not None and entry.measured_cop > 0
        ]

        if not cop_values:
            return None

        # Need at least 3 days of data for a meaningful average
        if len(cop_values) < 3:
            return None

        return sum(cop_values) / len(cop_values)

    def update_efficiency_factor(self, new_factor: float) -> None:
        """Update the efficiency factor dynamically.

        Used for heat pumps with dynamic COP calculation where the
        effective COP changes based on measured data.

        Args:
            new_factor: The new efficiency factor (COP for heat pumps)
        """
        if new_factor > 0:
            self.efficiency_factor = new_factor

    @property
    def total_energy_kwh(self) -> float:
        """Get total cumulative energy in kWh."""
        return self._total_energy_kwh

    def add_data_point(
        self,
        point: ThermalDataPoint,
        measured_energy_kwh: float | None = None,
    ) -> None:
        """Add a new data point and update calculations.

        Args:
            point: The thermal data point
            measured_energy_kwh: Energy measured from external sensor (for energy-based sources)
        """
        # Track heating time
        if self._last_point is not None and self._last_point.heating_on:
            time_delta_hours = (point.timestamp - self._last_point.timestamp) / SECONDS_PER_HOUR
            if time_delta_hours > 0:
                self._total_heating_hours += time_delta_hours

                # Calculate energy: use measured if available, otherwise estimate from power
                if measured_energy_kwh is not None:
                    # Energy-based source: use provided energy increment
                    self._measured_energy_kwh += measured_energy_kwh
                    self._total_energy_kwh += measured_energy_kwh
                elif self.heater_power is not None and self.heater_power > 0:
                    # Power-based source: estimate energy = Power × time
                    energy_kwh = (self.heater_power / 1000) * time_delta_hours
                    self._total_energy_kwh += energy_kwh

        self.data_points.append(point)
        self._last_point = point

        # Recalculate K if we have enough data
        if self.data_hours >= MIN_DATA_HOURS:
            self._calculate_k()

    def _calculate_k(self, period_energy_kwh: float | None = None) -> None:
        """Calculate K from aggregated data over the last AGGREGATION_PERIOD_HOURS.

        Args:
            period_energy_kwh: Measured energy for the period (from energy_sensor or power_sensor).
                               If None, will estimate from heater_power.

        Energy source priority (most accurate first):
        1. period_energy_kwh (external energy sensor - most accurate)
        2. _measured_energy_kwh (integrated from power sensor - accurate)
        3. heater_power × heating_hours (declared power - estimation)
        """
        if len(self.data_points) < 2:
            return

        now = self.data_points[-1].timestamp
        period_start = now - (AGGREGATION_PERIOD_HOURS * SECONDS_PER_HOUR)

        # Get points in the aggregation period
        period_points = [p for p in self.data_points if p.timestamp >= period_start]

        if len(period_points) < 10:  # Need minimum points for aggregation
            _LOGGER.debug("Not enough points for K calculation: %d", len(period_points))
            return

        # Calculate aggregated values - ALWAYS update aggregation even if K won't be calculated
        # This is needed for excellent inference detection (minimal heating case)
        aggregation = self._aggregate_period(period_points)
        self._last_aggregation = aggregation

        # Check minimum conditions for K calculation (but aggregation is still updated above)
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

        # Calculate energy for K calculation
        # Priority: measured energy (external) > measured energy (integrated) > estimated from power
        #
        # IMPORTANT: efficiency_factor converts consumed energy to thermal output:
        # - Electric (1.0): 1 kWh consumed = 1 kWh heat
        # - Heat pump (3.0): 1 kWh consumed = 3 kWh heat (COP)
        # - Gas boiler (0.9): 1 kWh gas = 0.9 kWh heat (combustion efficiency)
        # - Gas furnace (0.85): 1 kWh gas = 0.85 kWh heat (combustion + distribution losses)
        if period_energy_kwh is not None and period_energy_kwh > 0:
            # 1. External energy sensor (most accurate - actual consumption)
            # Apply efficiency_factor to convert to thermal energy
            energy_wh = period_energy_kwh * 1000 * self.efficiency_factor  # Convert kWh to Wh thermal
            energy_source = "energy_sensor"
        elif self._measured_energy_kwh > 0 and aggregation.heating_hours > 0:
            # 2. Integrated from power sensor (accurate - real power readings)
            # Scale measured energy to the aggregation period based on heating ratio
            # Apply efficiency_factor to convert to thermal energy
            energy_wh = self._measured_energy_kwh * 1000 * self.efficiency_factor  # Convert kWh to Wh thermal
            energy_source = "power_sensor"
        elif self.heater_power is not None and self.heater_power > 0:
            # 3. Estimated from declared power (least accurate)
            # Apply efficiency_factor to convert to thermal energy
            energy_wh = self.heater_power * aggregation.heating_hours * self.efficiency_factor
            energy_source = "heater_power"
        else:
            # Cannot calculate K without energy data
            _LOGGER.debug(
                "[%s] Cannot calculate K: no power or energy data available",
                self.zone_name,
            )
            return

        # K = Thermal Energy / (ΔT × duration)
        # K represents heat loss in W/°C (thermal watts, not electric watts)
        k = energy_wh / (aggregation.delta_t * aggregation.duration_hours)

        self._k_coefficient = k
        self._last_valid_k = k  # Preserve this valid K
        # Update last K date to today (real-time calculation)
        from datetime import datetime
        self._last_k_date = datetime.now().strftime("%Y-%m-%d")

        _LOGGER.info(
            "K calculated for %s: %.1f W/°C " "(energy=%.0f Wh [%s], ΔT=%.1f°C, duration=%.1fh, heating=%.1fh)",
            self.zone_name,
            k,
            energy_wh,
            energy_source,
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

    def add_daily_summary(
        self,
        date: str,
        heating_hours: float,
        avg_delta_t: float,
        energy_kwh: float,
        avg_indoor_temp: float,
        avg_outdoor_temp: float,
        sample_count: int,
        k_7d: float | None = None,
        temp_variation: float | None = None,
        avg_wind_speed: float | None = None,
        dominant_wind_direction: str | None = None,
        measured_cop: float | None = None,
    ) -> None:
        """Archive a day's data into the rolling 7-day history.

        Called at midnight to store the previous day's aggregated data.
        Automatically removes entries older than LONG_TERM_HISTORY_DAYS (5 years).

        Args:
            date: ISO date string (YYYY-MM-DD)
            heating_hours: Total hours of heating that day
            avg_delta_t: Average temperature difference
            energy_kwh: Estimated energy consumption
            avg_indoor_temp: Average indoor temperature
            avg_outdoor_temp: Average outdoor temperature
            sample_count: Number of data samples
            k_7d: The K_7j score at time of archival (for historical graph)
            temp_variation: Indoor temperature variation (max - min) in °C
            avg_wind_speed: Average wind speed that day (km/h)
            dominant_wind_direction: Most frequent wind direction (N, NE, E, SE, S, SW, W, NW)
            measured_cop: Measured COP for heat pumps (for dynamic efficiency)
        """
        # Don't add if we don't have meaningful data
        if sample_count < 10:
            _LOGGER.debug(
                "[%s] Skipping daily archive for %s - insufficient samples (%d)", self.zone_name, date, sample_count
            )
            return

        # Check if we already have this date
        existing_dates = [e.date for e in self._daily_history]
        if date in existing_dates:
            _LOGGER.debug("[%s] Date %s already in history, skipping", self.zone_name, date)
            return

        # Create and add entry
        entry = DailyHistoryEntry(
            date=date,
            heating_hours=heating_hours,
            avg_delta_t=avg_delta_t,
            energy_kwh=energy_kwh,
            avg_indoor_temp=avg_indoor_temp,
            avg_outdoor_temp=avg_outdoor_temp,
            sample_count=sample_count,
            k_7d=k_7d,
            temp_variation=temp_variation,
            avg_wind_speed=avg_wind_speed,
            dominant_wind_direction=dominant_wind_direction,
            measured_cop=measured_cop,
        )
        self._daily_history.append(entry)

        # Sort by date and keep only last LONG_TERM_HISTORY_DAYS days (5 years)
        self._daily_history.sort(key=lambda e: e.date)
        while len(self._daily_history) > LONG_TERM_HISTORY_DAYS:
            removed = self._daily_history.pop(0)
            _LOGGER.debug("[%s] Removed oldest history entry: %s", self.zone_name, removed.date)

        _LOGGER.info(
            "[%s] 📅 Added daily summary for %s: %.1fh heating, ΔT=%.1f°C, %.2f kWh " "(history: %d days)",
            self.zone_name,
            date,
            heating_hours,
            avg_delta_t,
            energy_kwh,
            len(self._daily_history),
        )

        # Recalculate 7-day K coefficient
        self._calculate_k_from_history()

    def _calculate_k_from_history(self) -> None:
        """Calculate K coefficient from 7-day rolling history.

        This provides a stable K that doesn't reset at midnight.
        Uses weighted average based on sample count per day.
        Only uses the last HISTORY_DAYS (7) days for calculation.

        Energy source hierarchy (stored in daily history):
        1. energy_kwh from energy_sensor (measured - most accurate)
        2. energy_kwh from power_sensor integration (measured - accurate)
        3. energy_kwh estimated from heater_power × heating_hours (fallback)

        The coordinator stores the best available energy source in energy_kwh.
        """
        if not self._daily_history:
            return

        # Only use the last HISTORY_DAYS (7) days for K calculation
        recent_history = (
            self._daily_history[-HISTORY_DAYS:] if len(self._daily_history) > HISTORY_DAYS else self._daily_history
        )

        # Separate days into categories:
        # 1. Days with enough heating data (can calculate K directly)
        # 2. "Perfect" days: temp stable but very little heating (use K_min as estimate)
        # 3. Invalid days: not enough ΔT or unstable temp
        calculable_days = []
        perfect_days = []

        for d in recent_history:
            if d.avg_delta_t < MIN_DELTA_T:
                continue  # Not enough ΔT

            temp_stable = d.temp_variation is not None and d.temp_variation < TEMP_STABILITY_THRESHOLD
            has_enough_heating = d.heating_hours >= MIN_HEATING_TIME_HOURS
            has_minimal_heating = d.heating_hours >= 0.1  # At least 6 minutes

            # Check if indoor temp is comfortable (>= 17°C)
            temp_comfortable = d.avg_indoor_temp >= MIN_COMFORT_TEMP

            if has_enough_heating or (has_minimal_heating and temp_stable):
                # Can calculate K for this day
                calculable_days.append(d)
            elif temp_stable and temp_comfortable and d.heating_hours < 0.1:
                # "Perfect" day: stable AND comfortable temp with almost no heating
                # This proves excellent insulation - will use K_min as conservative estimate
                perfect_days.append(d)
            else:
                _LOGGER.debug(
                    "[%s] Day %s filtered: heating=%.2fh, temp_var=%s, indoor=%.1f°C, stable=%s, comfortable=%s",
                    self.zone_name,
                    d.date,
                    d.heating_hours,
                    f"{d.temp_variation:.1f}°C" if d.temp_variation else "N/A",
                    d.avg_indoor_temp,
                    temp_stable,
                    temp_comfortable,
                )

        # First pass: calculate K for days with enough heating data
        day_k_values = []
        for day in calculable_days:
            if day.energy_kwh > 0:
                energy_wh = day.energy_kwh * 1000 * self.efficiency_factor
            elif self.heater_power is not None and self.heater_power > 0:
                energy_wh = self.heater_power * day.heating_hours * self.efficiency_factor
            else:
                continue

            k_day = energy_wh / (day.avg_delta_t * 24)
            day_k_values.append((day, k_day))

            _LOGGER.debug(
                "[%s] Day %s: K=%.1f W/°C (heating=%.1fh, ΔT=%.1f°C, energy=%.2f kWh)",
                self.zone_name,
                day.date,
                k_day,
                day.heating_hours,
                day.avg_delta_t,
                day.energy_kwh,
            )

        # Find minimum K from calculable days (or use current K_24h as fallback)
        k_min = None
        if day_k_values:
            k_min = min(k for _, k in day_k_values)
        elif self._k_coefficient is not None:
            k_min = self._k_coefficient

        # Add "perfect" days using K_min as estimate
        # Logic: if temp is stable with no heating, K must be <= K_min
        if k_min is not None and perfect_days:
            for day in perfect_days:
                day_k_values.append((day, k_min))
                _LOGGER.info(
                    "[%s] Day %s: K=%.1f W/°C (PERFECT day - using K_min, heating=%.1fmin, indoor=%.1f°C, temp_var=%.1f°C)",
                    self.zone_name,
                    day.date,
                    k_min,
                    day.heating_hours * 60,
                    day.avg_indoor_temp,
                    day.temp_variation or 0,
                )

        if not day_k_values:
            _LOGGER.debug(
                "[%s] No valid days in history for K calculation (%d days total)",
                self.zone_name,
                len(self._daily_history),
            )
            return

        # Calculate weighted average
        total_weighted_k = 0.0
        total_weight = 0.0

        for day, k_day in day_k_values:
            weight = day.sample_count
            total_weighted_k += k_day * weight
            total_weight += weight

        if total_weight > 0:
            self._k_coefficient_7d = total_weighted_k / total_weight
            self._last_valid_k = self._k_coefficient_7d  # Update last valid K
            # Track the most recent day used in the calculation
            all_days = [day for day, _ in day_k_values]
            self._last_k_date = all_days[-1].date if all_days else None

            _LOGGER.info(
                "[%s] 📊 7-day K coefficient: %.1f W/°C (from %d days: %d calculated + %d perfect, last: %s)",
                self.zone_name,
                self._k_coefficient_7d,
                len(day_k_values),
                len(calculable_days),
                len(perfect_days),
                self._last_k_date,
            )

    def clear_history(self) -> None:
        """Clear 7-day history data for manual reset.

        Use this when:
        - User completed insulation work and wants fresh measurement
        - User changed windows/doors
        - User wants to reset anomalous data
        """
        old_count = len(self._daily_history)
        self._daily_history.clear()
        self._k_coefficient_7d = None
        # Don't clear _last_valid_k - keep it as reference

        _LOGGER.info(
            "[%s] 🔄 History cleared (%d days removed). Last valid K preserved: %.1f W/°C",
            self.zone_name,
            old_count,
            self._last_valid_k or 0,
        )

    def clear_all(self) -> None:
        """Clear ALL calibration data for complete reset.

        Use this when:
        - Measurements were taken during unusual conditions
        - User changed heating equipment
        - User wants to start fresh calibration from scratch

        This resets everything including:
        - 7-day rolling history
        - 24h rolling data points
        - All K coefficients
        - Energy counters
        - Last valid K reference
        """
        history_count = len(self._daily_history)
        points_count = len(self.data_points)

        # Clear all data
        self._daily_history.clear()
        self.data_points.clear()
        self._k_coefficient = None
        self._k_coefficient_7d = None
        self._last_valid_k = None
        self._last_k_date = None
        self._last_aggregation = None
        self._total_energy_kwh = 0.0
        self._last_point = None

        _LOGGER.info(
            "[%s] 🗑️ COMPLETE RESET: Cleared %d history days, %d data points, all K coefficients",
            self.zone_name,
            history_count,
            points_count,
        )

    def get_analysis(self) -> dict[str, Any]:
        """Get current analysis results."""
        agg = self._last_aggregation

        # Calculate daily energy
        daily_energy_kwh = None
        if agg:
            if self.heater_power is not None and self.heater_power > 0:
                daily_energy_kwh = self.heater_power * agg.heating_hours / 1000
            elif self._measured_energy_kwh > 0 and self._total_heating_hours > 0:
                # Estimate from measured energy ratio
                daily_energy_kwh = (
                    self._measured_energy_kwh * (agg.heating_hours / self._total_heating_hours)
                    if self._total_heating_hours > 0
                    else None
                )

        return {
            # Main coefficient (prefers 7-day stable K)
            "k_coefficient": self.k_coefficient,  # Uses property that prefers 7d
            "k_coefficient_24h": self._k_coefficient,  # Real-time 24h K
            "k_coefficient_7d": self._k_coefficient_7d,  # Stable 7-day K
            "k_per_m2": self.k_per_m2,
            "k_per_m3": self.k_per_m3,
            # Aggregation data (current 24h period)
            "heating_hours": agg.heating_hours if agg else None,
            "heating_ratio": agg.heating_ratio if agg else None,
            "avg_delta_t": agg.delta_t if agg else None,
            "daily_energy_kwh": daily_energy_kwh,
            # Cumulative energy (for Energy Dashboard)
            "total_energy_kwh": self._total_energy_kwh,
            "measured_energy_kwh": self._measured_energy_kwh,
            # Status
            "data_hours": self.data_hours,
            "samples_count": self.samples_count,
            "data_ready": self.data_hours >= MIN_DATA_HOURS,
            # History status
            "history_days": len(self._daily_history),
            "history_has_valid_k": self._k_coefficient_7d is not None,
            "last_k_date": self._last_k_date,
            # Configuration and derived values
            "heater_power": self.heater_power,
            "effective_power": self.effective_power,
            "derived_power": self.derived_power,
            "efficiency_factor": self.efficiency_factor,
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

    def get_season_status(self) -> str:
        """Determine current season status based on ΔT.

        Returns:
            SEASON_SUMMER: T° ext > T° int (negative ΔT)
            SEASON_OFF: 0 < ΔT < MIN_DELTA_T
            SEASON_HEATING: ΔT >= MIN_DELTA_T (can calculate K)
        """
        if not self._last_aggregation:
            # No data yet, assume heating season
            return SEASON_HEATING

        delta_t = self._last_aggregation.delta_t

        if delta_t < 0:
            return SEASON_SUMMER
        elif delta_t < MIN_DELTA_T:
            return SEASON_OFF
        else:
            return SEASON_HEATING

    def get_temp_stability(self) -> dict[str, Any]:
        """Analyze indoor temperature stability over the aggregation period.

        Returns dict with:
            - stable: bool - True if temp variation < TEMP_STABILITY_THRESHOLD
            - min_temp: float - Minimum indoor temp
            - max_temp: float - Maximum indoor temp
            - variation: float - max - min
        """
        if len(self.data_points) < 10:
            return {"stable": False, "min_temp": None, "max_temp": None, "variation": None}

        now = self.data_points[-1].timestamp
        period_start = now - (AGGREGATION_PERIOD_HOURS * SECONDS_PER_HOUR)
        period_points = [p for p in self.data_points if p.timestamp >= period_start]

        if len(period_points) < 10:
            return {"stable": False, "min_temp": None, "max_temp": None, "variation": None}

        indoor_temps = [p.indoor_temp for p in period_points]
        min_temp = min(indoor_temps)
        max_temp = max(indoor_temps)
        variation = max_temp - min_temp

        return {
            "stable": variation < TEMP_STABILITY_THRESHOLD,
            "min_temp": min_temp,
            "max_temp": max_temp,
            "variation": variation,
        }

    def is_excellent_by_inference(self) -> bool:
        """Check if excellent isolation can be inferred.

        Conditions for inference:
        1. At least 24h of data
        2. ΔT >= MIN_DELTA_T (it's cold outside)
        3. Heating time < MIN_HEATING_TIME_HOURS (radiator barely ran)
        4. Indoor temperature is stable (room maintains temp)

        If all conditions met, the room is excellently insulated!
        """
        # Need enough data
        if self.data_hours < EXCELLENT_INFERENCE_MIN_HOURS:
            return False

        # Need aggregation data
        if not self._last_aggregation:
            return False

        agg = self._last_aggregation

        # Must be heating season (ΔT >= 5°C)
        if agg.delta_t < MIN_DELTA_T:
            return False

        # Radiator must have run very little
        if agg.heating_hours >= MIN_HEATING_TIME_HOURS:
            return False

        # Temperature must be stable
        stability = self.get_temp_stability()
        if not stability["stable"]:
            return False

        _LOGGER.info(
            "[%s] 🏆 Excellent isolation inferred: ΔT=%.1f°C, heating=%.1fmin, temp_variation=%.1f°C",
            self.zone_name,
            agg.delta_t,
            agg.heating_hours * 60,
            stability["variation"],
        )
        return True

    def get_insulation_status(self) -> dict[str, Any]:
        """Get comprehensive insulation status.

        Returns dict with:
            - status: str - One of INSULATION_* constants
            - rating: str | None - Insulation rating (excellent, good, etc.)
            - k_value: float | None - K coefficient (current or last valid)
            - k_source: str - "calculated", "inferred", "last_valid", None
            - season: str - Current season status
            - message: str - Human-readable status message
        """
        season = self.get_season_status()
        stability = self.get_temp_stability()

        # Case 1: Not enough data yet
        if self.data_hours < MIN_DATA_HOURS:
            return {
                "status": INSULATION_WAITING_DATA,
                "rating": None,
                "k_value": self._last_valid_k,
                "k_source": "last_valid" if self._last_valid_k else None,
                "season": season,
                "message": "Data collection in progress",
                "temp_stable": stability["stable"],
            }

        # Case 2: Summer mode (T° ext > T° int)
        if season == SEASON_SUMMER:
            return {
                "status": INSULATION_WAITING_DATA,
                "rating": self.get_insulation_rating() if self._last_valid_k else None,
                "k_value": self._last_valid_k,
                "k_source": "last_valid" if self._last_valid_k else None,
                "season": season,
                "message": "Summer mode - measurement not possible",
                "temp_stable": stability["stable"],
            }

        # Case 3: Off-season (ΔT too low)
        if season == SEASON_OFF:
            return {
                "status": INSULATION_WAITING_DATA,
                "rating": self.get_insulation_rating() if self._last_valid_k else None,
                "k_value": self._last_valid_k,
                "k_source": "last_valid" if self._last_valid_k else None,
                "season": season,
                "message": "Shoulder season - ΔT insufficient",
                "temp_stable": stability["stable"],
            }

        # Case 4: K is calculated
        if self._k_coefficient is not None:
            return {
                "status": INSULATION_CALCULATED,
                "rating": self.get_insulation_rating(),
                "k_value": self._k_coefficient,
                "k_source": "calculated",
                "season": season,
                "message": None,
                "temp_stable": stability["stable"],
            }

        # Case 5: Excellent by inference
        if self.is_excellent_by_inference():
            return {
                "status": INSULATION_EXCELLENT_INFERRED,
                "rating": "excellent_inferred",
                "k_value": None,  # Can't calculate, but we know it's very low
                "k_source": "inferred",
                "season": season,
                "message": "Excellent - minimal heating needed",
                "temp_stable": True,
            }

        # Case 6: Waiting for heating
        agg = self._last_aggregation
        if agg and not stability["stable"]:
            return {
                "status": INSULATION_WAITING_HEAT,
                "rating": None,
                "k_value": self._last_valid_k,
                "k_source": "last_valid" if self._last_valid_k else None,
                "season": season,
                "message": "Insufficient heating - unstable temperature",
                "temp_stable": False,
            }

        return {
            "status": INSULATION_WAITING_HEAT,
            "rating": None,
            "k_value": self._last_valid_k,
            "k_source": "last_valid" if self._last_valid_k else None,
            "season": season,
            "message": "Waiting for heating",
            "temp_stable": stability["stable"],
        }

    @property
    def last_valid_k(self) -> float | None:
        """Get last valid K coefficient (preserved during off-season)."""
        return self._last_valid_k

    def to_dict(self) -> dict[str, Any]:
        """Export model state to dictionary for persistence."""
        return {
            "data_points": [
                {
                    "timestamp": p.timestamp,
                    "indoor_temp": p.indoor_temp,
                    "outdoor_temp": p.outdoor_temp,
                    "heating_on": p.heating_on,
                }
                for p in self.data_points
            ],
            "k_coefficient": self._k_coefficient,
            "k_coefficient_7d": self._k_coefficient_7d,
            "last_valid_k": self._last_valid_k,
            "last_k_date": self._last_k_date,
            "total_energy_kwh": self._total_energy_kwh,
            "last_point": (
                {
                    "timestamp": self._last_point.timestamp,
                    "indoor_temp": self._last_point.indoor_temp,
                    "outdoor_temp": self._last_point.outdoor_temp,
                    "heating_on": self._last_point.heating_on,
                }
                if self._last_point
                else None
            ),
            # 7-day history for stable K calculation
            "daily_history": [entry.to_dict() for entry in self._daily_history],
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """Restore model state from dictionary.

        Backward compatible: handles data from versions without daily_history.
        """
        if not data:
            return

        # Restore data points
        if "data_points" in data:
            self.data_points.clear()
            for p in data["data_points"]:
                self.data_points.append(
                    ThermalDataPoint(
                        timestamp=p["timestamp"],
                        indoor_temp=p["indoor_temp"],
                        outdoor_temp=p["outdoor_temp"],
                        heating_on=p["heating_on"],
                    )
                )

        # Restore calculated values
        if "k_coefficient" in data:
            self._k_coefficient = data["k_coefficient"]

        # Restore 7-day K (new in v1.2.0)
        if "k_coefficient_7d" in data:
            self._k_coefficient_7d = data["k_coefficient_7d"]

        if "last_valid_k" in data:
            self._last_valid_k = data["last_valid_k"]
        elif self._k_coefficient_7d is not None:
            # Prefer 7-day K as last valid
            self._last_valid_k = self._k_coefficient_7d
        elif self._k_coefficient is not None:
            # Backward compatibility: use k_coefficient as last_valid_k
            self._last_valid_k = self._k_coefficient

        if "last_k_date" in data:
            self._last_k_date = data["last_k_date"]

        if "total_energy_kwh" in data:
            self._total_energy_kwh = data["total_energy_kwh"]

        # Restore last point
        if data.get("last_point"):
            lp = data["last_point"]
            self._last_point = ThermalDataPoint(
                timestamp=lp["timestamp"],
                indoor_temp=lp["indoor_temp"],
                outdoor_temp=lp["outdoor_temp"],
                heating_on=lp["heating_on"],
            )

        # Restore 7-day history (new in v1.2.0, backward compatible)
        if "daily_history" in data:
            self._daily_history.clear()
            for entry_data in data["daily_history"]:
                try:
                    entry = DailyHistoryEntry.from_dict(entry_data)
                    self._daily_history.append(entry)
                except (KeyError, TypeError) as err:
                    _LOGGER.warning("[%s] Could not restore history entry: %s", self.zone_name, err)
            # Sort by date
            self._daily_history.sort(key=lambda e: e.date)
            _LOGGER.info("[%s] Restored %d days of history", self.zone_name, len(self._daily_history))

        # Recalculate aggregation if we have data
        if self.data_hours >= MIN_DATA_HOURS:
            self._calculate_k()

        # Recalculate 7-day K from history if available
        if self._daily_history:
            self._calculate_k_from_history()

        _LOGGER.info(
            "Restored %d data points for %s (%.1fh of data, K_24h=%.1f, K_7d=%.1f W/°C, %d history days)",
            len(self.data_points),
            self.zone_name,
            self.data_hours,
            self._k_coefficient or 0,
            self._k_coefficient_7d or 0,
            len(self._daily_history),
        )
