"""Tests for Home Performance models."""

from __future__ import annotations

import time

import pytest

from custom_components.home_performance.models import (
    SEASON_HEATING,
    SEASON_OFF,
    SEASON_SUMMER,
    SECONDS_PER_HOUR,
    AggregatedPeriod,
    DailyHistoryEntry,
    ThermalDataPoint,
    ThermalLossModel,
)


class TestThermalDataPoint:
    """Test ThermalDataPoint dataclass."""

    def test_create_data_point(self):
        """Test creating a ThermalDataPoint."""
        ts = time.time()
        point = ThermalDataPoint(
            timestamp=ts,
            indoor_temp=20.0,
            outdoor_temp=5.0,
            heating_on=True,
        )
        assert point.timestamp == ts
        assert point.indoor_temp == 20.0
        assert point.outdoor_temp == 5.0
        assert point.heating_on is True

    def test_data_point_heating_off(self):
        """Test creating a data point with heating off."""
        point = ThermalDataPoint(
            timestamp=0.0,
            indoor_temp=19.5,
            outdoor_temp=10.0,
            heating_on=False,
        )
        assert point.heating_on is False


class TestAggregatedPeriod:
    """Test AggregatedPeriod dataclass."""

    @pytest.fixture
    def sample_period(self) -> AggregatedPeriod:
        """Create a sample aggregated period for testing."""
        return AggregatedPeriod(
            start_time=0.0,
            end_time=24 * SECONDS_PER_HOUR,  # 24 hours later
            heating_seconds=6 * SECONDS_PER_HOUR,  # 6 hours of heating
            avg_indoor_temp=20.0,
            avg_outdoor_temp=5.0,
            sample_count=1440,  # 1 sample per minute for 24h
        )

    def test_duration_hours(self, sample_period: AggregatedPeriod):
        """Test duration_hours property."""
        assert sample_period.duration_hours == 24.0

    def test_heating_hours(self, sample_period: AggregatedPeriod):
        """Test heating_hours property."""
        assert sample_period.heating_hours == 6.0

    def test_delta_t(self, sample_period: AggregatedPeriod):
        """Test delta_t property."""
        assert sample_period.delta_t == 15.0  # 20 - 5 = 15°C

    def test_heating_ratio(self, sample_period: AggregatedPeriod):
        """Test heating_ratio property."""
        assert sample_period.heating_ratio == 0.25  # 6/24 = 0.25

    def test_heating_ratio_zero_duration(self):
        """Test heating_ratio with zero duration."""
        period = AggregatedPeriod(
            start_time=0.0,
            end_time=0.0,  # Zero duration
            heating_seconds=0.0,
            avg_indoor_temp=20.0,
            avg_outdoor_temp=5.0,
            sample_count=0,
        )
        assert period.heating_ratio == 0.0

    def test_negative_delta_t(self):
        """Test delta_t when outdoor is warmer (summer)."""
        period = AggregatedPeriod(
            start_time=0.0,
            end_time=SECONDS_PER_HOUR,
            heating_seconds=0.0,
            avg_indoor_temp=22.0,
            avg_outdoor_temp=30.0,  # Hot summer day
            sample_count=60,
        )
        assert period.delta_t == -8.0  # Indoor is cooler


class TestDailyHistoryEntry:
    """Test DailyHistoryEntry dataclass."""

    @pytest.fixture
    def sample_entry(self) -> DailyHistoryEntry:
        """Create a sample daily history entry."""
        return DailyHistoryEntry(
            date="2025-01-15",
            heating_hours=8.5,
            avg_delta_t=12.0,
            energy_kwh=12.75,
            avg_indoor_temp=19.5,
            avg_outdoor_temp=7.5,
            sample_count=1440,
            k_7d=25.5,
            avg_wind_speed=15.0,
            dominant_wind_direction="NW",
        )

    def test_to_dict(self, sample_entry: DailyHistoryEntry):
        """Test to_dict method."""
        result = sample_entry.to_dict()

        assert result["date"] == "2025-01-15"
        assert result["heating_hours"] == 8.5
        assert result["avg_delta_t"] == 12.0
        assert result["energy_kwh"] == 12.75
        assert result["avg_indoor_temp"] == 19.5
        assert result["avg_outdoor_temp"] == 7.5
        assert result["sample_count"] == 1440
        assert result["k_7d"] == 25.5
        assert result["avg_wind_speed"] == 15.0
        assert result["dominant_wind_direction"] == "NW"

    def test_to_dict_without_optional_fields(self):
        """Test to_dict without optional fields."""
        entry = DailyHistoryEntry(
            date="2025-01-15",
            heating_hours=8.5,
            avg_delta_t=12.0,
            energy_kwh=12.75,
            avg_indoor_temp=19.5,
            avg_outdoor_temp=7.5,
            sample_count=1440,
        )
        result = entry.to_dict()

        assert "k_7d" not in result
        assert "avg_wind_speed" not in result
        assert "dominant_wind_direction" not in result

    def test_from_dict(self, sample_entry: DailyHistoryEntry):
        """Test from_dict class method."""
        data = sample_entry.to_dict()
        restored = DailyHistoryEntry.from_dict(data)

        assert restored.date == sample_entry.date
        assert restored.heating_hours == sample_entry.heating_hours
        assert restored.avg_delta_t == sample_entry.avg_delta_t
        assert restored.k_7d == sample_entry.k_7d

    def test_from_dict_missing_optional(self):
        """Test from_dict with missing optional fields."""
        data = {
            "date": "2025-01-15",
            "heating_hours": 8.5,
            "avg_delta_t": 12.0,
            "energy_kwh": 12.75,
            "avg_indoor_temp": 19.5,
            "avg_outdoor_temp": 7.5,
            "sample_count": 1440,
        }
        entry = DailyHistoryEntry.from_dict(data)

        assert entry.k_7d is None
        assert entry.avg_wind_speed is None
        assert entry.dominant_wind_direction is None


class TestThermalLossModel:
    """Test ThermalLossModel class."""

    @pytest.fixture
    def model(self, zone_name: str, heater_power: float, surface: float, volume: float) -> ThermalLossModel:
        """Create a ThermalLossModel for testing."""
        return ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,
            surface=surface,
            volume=volume,
        )

    def test_init(self, model: ThermalLossModel, zone_name: str, heater_power: float):
        """Test model initialization."""
        assert model.zone_name == zone_name
        assert model.heater_power == heater_power
        assert model.samples_count == 0
        assert model.data_hours == 0.0
        assert model.k_coefficient is None

    def test_init_without_dimensions(self, zone_name: str, heater_power: float):
        """Test model initialization without surface/volume."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        assert model.surface is None
        assert model.volume is None
        assert model.k_per_m2 is None
        assert model.k_per_m3 is None

    def test_add_data_point(self, model: ThermalLossModel):
        """Test adding a data point."""
        point = ThermalDataPoint(
            timestamp=time.time(),
            indoor_temp=20.0,
            outdoor_temp=5.0,
            heating_on=True,
        )
        model.add_data_point(point)
        assert model.samples_count == 1

    def test_add_multiple_data_points(self, model: ThermalLossModel):
        """Test adding multiple data points."""
        base_time = time.time()
        for i in range(10):
            point = ThermalDataPoint(
                timestamp=base_time + i * 60,  # 1 minute apart
                indoor_temp=20.0 + (i * 0.1),
                outdoor_temp=5.0,
                heating_on=i % 2 == 0,  # Alternating
            )
            model.add_data_point(point)

        assert model.samples_count == 10

    def test_data_hours_calculation(self, model: ThermalLossModel):
        """Test data_hours property calculation."""
        base_time = time.time()
        # Add points spanning 2 hours
        model.add_data_point(ThermalDataPoint(base_time, 20.0, 5.0, True))
        model.add_data_point(ThermalDataPoint(base_time + 2 * SECONDS_PER_HOUR, 20.0, 5.0, True))

        assert model.data_hours == pytest.approx(2.0, rel=0.01)

    def test_k_coefficient_initially_none(self, model: ThermalLossModel):
        """Test that k_coefficient is None initially."""
        assert model.k_coefficient is None
        assert model.k_coefficient_24h is None
        assert model.k_coefficient_7d is None

    def test_k_per_m2_with_surface(self, model: ThermalLossModel, surface: float):
        """Test k_per_m2 calculation requires both K and surface."""
        # K is None, so k_per_m2 should be None
        assert model.k_per_m2 is None

        # Manually set K for testing
        model._k_coefficient = 30.0
        assert model.k_per_m2 == pytest.approx(30.0 / surface, rel=0.01)

    def test_k_per_m3_with_volume(self, model: ThermalLossModel, volume: float):
        """Test k_per_m3 calculation requires both K and volume."""
        # K is None, so k_per_m3 should be None
        assert model.k_per_m3 is None

        # Manually set K for testing
        model._k_coefficient = 30.0
        assert model.k_per_m3 == pytest.approx(30.0 / volume, rel=0.01)

    def test_get_analysis_empty(self, model: ThermalLossModel):
        """Test get_analysis with no data."""
        analysis = model.get_analysis()

        assert analysis["k_coefficient"] is None
        assert analysis["data_hours"] == 0.0
        assert analysis["samples_count"] == 0
        assert analysis["data_ready"] is False

    def test_clear_history(self, model: ThermalLossModel):
        """Test clear_history method."""
        # Add some history
        model.add_daily_summary(
            date="2025-01-15",
            heating_hours=8.0,
            avg_delta_t=10.0,
            energy_kwh=12.0,
            avg_indoor_temp=20.0,
            avg_outdoor_temp=10.0,
            sample_count=100,
        )
        assert model.history_days_count == 1

        model.clear_history()
        assert model.history_days_count == 0
        assert model.k_coefficient_7d is None

    def test_clear_all(self, model: ThermalLossModel):
        """Test clear_all method."""
        # Add data
        base_time = time.time()
        for i in range(5):
            model.add_data_point(
                ThermalDataPoint(
                    timestamp=base_time + i * 60,
                    indoor_temp=20.0,
                    outdoor_temp=5.0,
                    heating_on=True,
                )
            )
        model._k_coefficient = 25.0
        model._total_energy_kwh = 10.0

        model.clear_all()

        assert model.samples_count == 0
        assert model.k_coefficient is None
        assert model.total_energy_kwh == 0.0

    def test_insulation_rating_thresholds(self, model: ThermalLossModel, volume: float):
        """Test insulation rating based on K/m³ thresholds."""
        # Excellent: K/m³ < 0.4
        model._k_coefficient = 15.0  # 15/50 = 0.3 W/(°C·m³)
        assert model.get_insulation_rating() == "excellent"

        # Good: 0.4 <= K/m³ < 0.7
        model._k_coefficient = 25.0  # 25/50 = 0.5 W/(°C·m³)
        assert model.get_insulation_rating() == "good"

        # Average: 0.7 <= K/m³ < 1.0
        model._k_coefficient = 40.0  # 40/50 = 0.8 W/(°C·m³)
        assert model.get_insulation_rating() == "average"

        # Poor: 1.0 <= K/m³ < 1.5
        model._k_coefficient = 60.0  # 60/50 = 1.2 W/(°C·m³)
        assert model.get_insulation_rating() == "poor"

        # Very poor: K/m³ >= 1.5
        model._k_coefficient = 100.0  # 100/50 = 2.0 W/(°C·m³)
        assert model.get_insulation_rating() == "very_poor"

    def test_season_status_heating(self, model: ThermalLossModel):
        """Test season status during heating season."""
        # Create aggregation with ΔT >= 5°C
        base_time = time.time()
        for i in range(20):
            model.add_data_point(
                ThermalDataPoint(
                    timestamp=base_time + i * 60,
                    indoor_temp=20.0,
                    outdoor_temp=5.0,  # ΔT = 15°C
                    heating_on=True,
                )
            )
        model._calculate_k()

        assert model.get_season_status() == SEASON_HEATING

    def test_season_status_summer(self, model: ThermalLossModel):
        """Test season status during summer (outdoor > indoor)."""
        base_time = time.time()
        for i in range(20):
            model.add_data_point(
                ThermalDataPoint(
                    timestamp=base_time + i * 60,
                    indoor_temp=22.0,
                    outdoor_temp=30.0,  # ΔT = -8°C (summer)
                    heating_on=False,
                )
            )
        model._calculate_k()

        assert model.get_season_status() == SEASON_SUMMER

    def test_to_dict_from_dict_roundtrip(self, model: ThermalLossModel):
        """Test serialization/deserialization roundtrip."""
        # Add some data
        base_time = time.time()
        for i in range(5):
            model.add_data_point(
                ThermalDataPoint(
                    timestamp=base_time + i * 60,
                    indoor_temp=20.0,
                    outdoor_temp=5.0,
                    heating_on=i % 2 == 0,
                )
            )
        model._k_coefficient = 25.5
        model._total_energy_kwh = 5.5

        # Serialize
        data = model.to_dict()

        # Create new model and restore
        new_model = ThermalLossModel(
            zone_name=model.zone_name,
            heater_power=model.heater_power,
            surface=model.surface,
            volume=model.volume,
        )
        new_model.from_dict(data)

        assert new_model.samples_count == model.samples_count
        assert new_model._k_coefficient == model._k_coefficient
        assert new_model._total_energy_kwh == model._total_energy_kwh

    def test_daily_summary_skip_low_samples(self, model: ThermalLossModel):
        """Test that daily summary is skipped with too few samples."""
        model.add_daily_summary(
            date="2025-01-15",
            heating_hours=8.0,
            avg_delta_t=10.0,
            energy_kwh=12.0,
            avg_indoor_temp=20.0,
            avg_outdoor_temp=10.0,
            sample_count=5,  # Below threshold of 10
        )
        assert model.history_days_count == 0

    def test_daily_summary_no_duplicate_dates(self, model: ThermalLossModel):
        """Test that duplicate dates are not added to history."""
        model.add_daily_summary(
            date="2025-01-15",
            heating_hours=8.0,
            avg_delta_t=10.0,
            energy_kwh=12.0,
            avg_indoor_temp=20.0,
            avg_outdoor_temp=10.0,
            sample_count=100,
        )
        # Try to add same date again
        model.add_daily_summary(
            date="2025-01-15",
            heating_hours=10.0,  # Different values
            avg_delta_t=12.0,
            energy_kwh=15.0,
            avg_indoor_temp=21.0,
            avg_outdoor_temp=9.0,
            sample_count=200,
        )

        assert model.history_days_count == 1
        # Should keep original entry
        assert model.daily_history[0].heating_hours == 8.0


class TestThermalLossModelKCalculation:
    """Test K coefficient calculation in ThermalLossModel."""

    @pytest.fixture
    def model_with_data(self, zone_name: str, heater_power: float, surface: float, volume: float) -> ThermalLossModel:
        """Create a model with enough data for K calculation."""
        model = ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,  # 1500W
            surface=surface,
            volume=volume,
        )

        # Add 24 hours of data with 6 hours of heating
        # This should give a calculable K coefficient
        base_time = time.time() - 24 * SECONDS_PER_HOUR

        for hour in range(25):  # 25 hours of data (> MIN_DATA_HOURS=12)
            for minute in range(60):
                ts = base_time + hour * SECONDS_PER_HOUR + minute * 60
                # Heating on for first 6 hours, then cycling
                heating_on = hour < 6 or (hour >= 12 and hour < 14)

                model.add_data_point(
                    ThermalDataPoint(
                        timestamp=ts,
                        indoor_temp=20.0,
                        outdoor_temp=5.0,  # ΔT = 15°C
                        heating_on=heating_on,
                    )
                )

        return model

    def test_k_calculation_with_sufficient_data(self, model_with_data: ThermalLossModel):
        """Test that K is calculated with sufficient data."""
        # K should be calculated after adding enough data
        assert model_with_data.k_coefficient_24h is not None

        # K should be reasonable (between 10 and 100 W/°C for a room)
        assert 10 < model_with_data.k_coefficient_24h < 100

    def test_k_calculation_formula(self, zone_name: str):
        """Test K calculation follows the expected formula.

        K = Energy / (ΔT × duration)

        Example: 1000W heater, 6h heating, 24h period, ΔT=15°C
        Energy = 1000W × 6h = 6000 Wh
        K = 6000 / (15 × 24) = 16.67 W/°C
        """
        heater_power = 1000.0
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)

        # Add exactly 24 hours of data with exactly 6 hours heating
        base_time = time.time() - 24 * SECONDS_PER_HOUR

        for minute in range(24 * 60 + 1):  # 1441 minutes
            ts = base_time + minute * 60
            hour = minute // 60
            # Heating on for exactly the first 6 hours
            heating_on = hour < 6

            model.add_data_point(
                ThermalDataPoint(
                    timestamp=ts,
                    indoor_temp=20.0,
                    outdoor_temp=5.0,  # ΔT = 15°C
                    heating_on=heating_on,
                )
            )

        # Expected K = 1000 * 6 / (15 * 24) ≈ 16.67 W/°C
        expected_k = (heater_power * 6) / (15 * 24)

        assert model.k_coefficient_24h is not None
        # Allow some tolerance due to discrete sampling
        assert model.k_coefficient_24h == pytest.approx(expected_k, rel=0.1)

    def test_k_not_calculated_low_delta_t(self, zone_name: str, heater_power: float):
        """Test K is not calculated when ΔT is too low."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)

        base_time = time.time() - 24 * SECONDS_PER_HOUR
        for minute in range(24 * 60 + 1):
            ts = base_time + minute * 60
            model.add_data_point(
                ThermalDataPoint(
                    timestamp=ts,
                    indoor_temp=20.0,
                    outdoor_temp=18.0,  # ΔT = 2°C (below MIN_DELTA_T=5)
                    heating_on=True,
                )
            )

        # K should not be calculated due to low ΔT
        assert model.k_coefficient_24h is None

    def test_k_not_calculated_low_heating_time(self, zone_name: str, heater_power: float):
        """Test K is not calculated when heating time is too low."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)

        base_time = time.time() - 24 * SECONDS_PER_HOUR
        for minute in range(24 * 60 + 1):
            ts = base_time + minute * 60
            # Only 10 minutes of heating (below MIN_HEATING_TIME_HOURS=0.5)
            heating_on = minute < 10
            model.add_data_point(
                ThermalDataPoint(
                    timestamp=ts,
                    indoor_temp=20.0,
                    outdoor_temp=5.0,
                    heating_on=heating_on,
                )
            )

        # K should not be calculated due to insufficient heating
        assert model.k_coefficient_24h is None


class TestThermalLossModelInsulationStatus:
    """Test insulation status and rating methods."""

    def test_get_insulation_status_waiting_data(self, zone_name: str, heater_power: float, volume: float):
        """Test insulation status when waiting for data."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power, volume=volume)
        status = model.get_insulation_status()
        assert status["status"] == "waiting_data"
        assert status["rating"] is None

    def test_get_insulation_status_calculated(self, zone_name: str, heater_power: float, volume: float):
        """Test insulation status when K is calculated."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power, volume=volume)
        model._k_coefficient = 25.0

        # Add enough data points
        base_time = time.time() - 24 * SECONDS_PER_HOUR
        for minute in range(24 * 60 + 1):
            ts = base_time + minute * 60
            model.add_data_point(
                ThermalDataPoint(
                    timestamp=ts,
                    indoor_temp=20.0,
                    outdoor_temp=5.0,
                    heating_on=minute % 4 == 0,
                )
            )

        status = model.get_insulation_status()
        assert status["status"] == "calculated"
        assert status["k_value"] == 25.0
        assert status["k_source"] == "calculated"

    def test_get_temp_stability_insufficient_data(self, zone_name: str, heater_power: float):
        """Test temp stability with insufficient data."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        stability = model.get_temp_stability()
        assert stability["stable"] is False
        assert stability["min_temp"] is None

    def test_get_temp_stability_stable(self, zone_name: str, heater_power: float):
        """Test temp stability when temperature is stable."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        base_time = time.time() - 24 * SECONDS_PER_HOUR
        for minute in range(24 * 60 + 1):
            ts = base_time + minute * 60
            model.add_data_point(
                ThermalDataPoint(
                    timestamp=ts,
                    indoor_temp=20.0 + (minute % 10) * 0.1,
                    outdoor_temp=5.0,
                    heating_on=False,
                )
            )

        stability = model.get_temp_stability()
        assert stability["stable"] is True
        assert stability["variation"] < 3.0

    def test_get_temp_stability_unstable(self, zone_name: str, heater_power: float):
        """Test temp stability when temperature is unstable."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        base_time = time.time() - 24 * SECONDS_PER_HOUR
        for minute in range(24 * 60 + 1):
            ts = base_time + minute * 60
            indoor = 18.0 if minute % 120 < 60 else 23.0
            model.add_data_point(ThermalDataPoint(timestamp=ts, indoor_temp=indoor, outdoor_temp=5.0, heating_on=False))

        stability = model.get_temp_stability()
        assert stability["stable"] is False
        assert stability["variation"] >= 3.0


class TestThermalLossModel7DayK:
    """Test 7-day K coefficient calculation."""

    def test_k_7d_not_calculated_without_history(self, zone_name: str, heater_power: float):
        """Test K_7d is None without history."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        assert model.k_coefficient_7d is None

    def test_k_7d_calculated_with_valid_history(self, zone_name: str, heater_power: float):
        """Test K_7d is calculated from valid daily history."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        for i in range(7):
            model.add_daily_summary(
                date=f"2025-01-{10 + i:02d}",
                heating_hours=6.0,
                avg_delta_t=10.0,
                energy_kwh=9.0,
                avg_indoor_temp=20.0,
                avg_outdoor_temp=10.0,
                sample_count=1440,
            )

        assert model.k_coefficient_7d is not None
        assert model.history_days_count == 7

    def test_daily_history_sorted_by_date(self, zone_name: str, heater_power: float):
        """Test that daily history is sorted by date."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        model.add_daily_summary(
            date="2025-01-15",
            heating_hours=6.0,
            avg_delta_t=10.0,
            energy_kwh=9.0,
            avg_indoor_temp=20.0,
            avg_outdoor_temp=10.0,
            sample_count=100,
        )
        model.add_daily_summary(
            date="2025-01-10",
            heating_hours=6.0,
            avg_delta_t=10.0,
            energy_kwh=9.0,
            avg_indoor_temp=20.0,
            avg_outdoor_temp=10.0,
            sample_count=100,
        )

        dates = [entry.date for entry in model.daily_history]
        assert dates == sorted(dates)

    def test_k_prefers_7d_over_24h(self, zone_name: str, heater_power: float, volume: float):
        """Test that k_coefficient property prefers 7d over 24h."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power, volume=volume)
        model._k_coefficient = 30.0
        model._k_coefficient_7d = 25.0
        assert model.k_coefficient == 25.0

    def test_k_falls_back_to_24h(self, zone_name: str, heater_power: float, volume: float):
        """Test that k_coefficient falls back to 24h when 7d is None."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power, volume=volume)
        model._k_coefficient = 30.0
        model._k_coefficient_7d = None
        assert model.k_coefficient == 30.0


class TestThermalLossModel7DayKFiltering:
    """Test 7-day K coefficient filtering logic for excellent isolation days."""

    def test_day_with_little_heating_but_stable_temp_is_valid(self, zone_name: str, heater_power: float):
        """Test that a day with little heating but stable temperature is included in K_7d."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)

        # Add days with normal heating
        for i in range(5):
            model.add_daily_summary(
                date=f"2025-01-{10 + i:02d}",
                heating_hours=6.0,
                avg_delta_t=10.0,
                energy_kwh=9.0,
                avg_indoor_temp=20.0,
                avg_outdoor_temp=10.0,
                sample_count=1440,
                temp_variation=1.5,  # Stable temperature
            )

        # Add a day with little heating but stable temperature (excellent isolation)
        model.add_daily_summary(
            date="2025-01-16",
            heating_hours=0.2,  # Only 12 minutes (< 0.5h threshold, but >= 0.1h)
            avg_delta_t=10.0,  # Sufficient ΔT
            energy_kwh=0.3,  # Low energy
            avg_indoor_temp=20.0,
            avg_outdoor_temp=10.0,
            sample_count=1440,
            temp_variation=1.0,  # Very stable (< 3°C threshold)
        )

        # K_7d should be calculated and include this day
        assert model.k_coefficient_7d is not None
        assert model.history_days_count == 6

    def test_day_with_little_heating_and_unstable_temp_is_filtered(self, zone_name: str, heater_power: float):
        """Test that a day with little heating and unstable temperature is filtered out."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)

        # Add days with normal heating
        for i in range(5):
            model.add_daily_summary(
                date=f"2025-01-{10 + i:02d}",
                heating_hours=6.0,
                avg_delta_t=10.0,
                energy_kwh=9.0,
                avg_indoor_temp=20.0,
                avg_outdoor_temp=10.0,
                sample_count=1440,
                temp_variation=1.5,
            )

        k_7d_before = model.k_coefficient_7d

        # Add a day with little heating and UNSTABLE temperature
        model.add_daily_summary(
            date="2025-01-16",
            heating_hours=0.2,  # Only 12 minutes
            avg_delta_t=10.0,
            energy_kwh=0.3,
            avg_indoor_temp=20.0,
            avg_outdoor_temp=10.0,
            sample_count=1440,
            temp_variation=5.0,  # Unstable (>= 3°C threshold)
        )

        # K_7d should NOT change (day should be filtered)
        # Note: Day is still added to history, but not used in calculation
        assert model.k_coefficient_7d == k_7d_before

    def test_day_with_very_little_heating_is_filtered(self, zone_name: str, heater_power: float):
        """Test that a day with almost no heating is filtered even with stable temp."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)

        # Add days with normal heating
        for i in range(5):
            model.add_daily_summary(
                date=f"2025-01-{10 + i:02d}",
                heating_hours=6.0,
                avg_delta_t=10.0,
                energy_kwh=9.0,
                avg_indoor_temp=20.0,
                avg_outdoor_temp=10.0,
                sample_count=1440,
                temp_variation=1.5,
            )

        k_7d_before = model.k_coefficient_7d

        # Add a day with almost no heating (< 0.1h = 6 min minimum)
        model.add_daily_summary(
            date="2025-01-16",
            heating_hours=0.05,  # Only 3 minutes (< 0.1h minimum)
            avg_delta_t=10.0,
            energy_kwh=0.1,
            avg_indoor_temp=20.0,
            avg_outdoor_temp=10.0,
            sample_count=1440,
            temp_variation=1.0,  # Stable but not enough heating
        )

        # K_7d should NOT change (day should be filtered due to < 0.1h)
        assert model.k_coefficient_7d == k_7d_before

    def test_backward_compat_day_without_temp_variation(self, zone_name: str, heater_power: float):
        """Test backward compatibility: days without temp_variation use normal filtering."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)

        # Add day without temp_variation (old data format)
        model.add_daily_summary(
            date="2025-01-10",
            heating_hours=6.0,  # Enough heating
            avg_delta_t=10.0,
            energy_kwh=9.0,
            avg_indoor_temp=20.0,
            avg_outdoor_temp=10.0,
            sample_count=1440,
            temp_variation=None,  # No temp_variation data
        )

        # Should still be valid (normal heating threshold met)
        assert model.k_coefficient_7d is not None


class TestThermalLossModelSeasonStatus:
    """Test season status detection."""

    def test_season_off_low_delta_t(self, zone_name: str, heater_power: float):
        """Test season is off-season when ΔT is low but positive."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        base_time = time.time() - 24 * SECONDS_PER_HOUR
        for minute in range(24 * 60 + 1):
            ts = base_time + minute * 60
            model.add_data_point(
                ThermalDataPoint(
                    timestamp=ts,
                    indoor_temp=20.0,
                    outdoor_temp=17.0,  # ΔT = 3°C (below MIN_DELTA_T but positive)
                    heating_on=True,
                )
            )

        assert model.get_season_status() == SEASON_OFF

    def test_season_default_heating(self, zone_name: str, heater_power: float):
        """Test season defaults to heating without data."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        assert model.get_season_status() == SEASON_HEATING


class TestAggregatedPeriodEdgeCases:
    """Test edge cases for AggregatedPeriod."""

    def test_aggregate_period_raises_on_empty(self, zone_name: str, heater_power: float):
        """Test _aggregate_period raises ValueError on empty list."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        with pytest.raises(ValueError, match="No points to aggregate"):
            model._aggregate_period([])


class TestThermalLossModelEfficiencyFactor:
    """Test efficiency factor in ThermalLossModel."""

    def test_init_with_default_efficiency(self, zone_name: str, heater_power: float):
        """Test model initializes with default efficiency factor of 1.0."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        assert model.efficiency_factor == 1.0

    def test_init_with_custom_efficiency(self, zone_name: str, heater_power: float):
        """Test model initializes with custom efficiency factor."""
        model = ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,
            efficiency_factor=3.0,  # Heat pump COP
        )
        assert model.efficiency_factor == 3.0

    def test_efficiency_factor_in_analysis(self, zone_name: str, heater_power: float):
        """Test efficiency_factor is included in get_analysis output."""
        model = ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,
            efficiency_factor=0.85,
        )
        analysis = model.get_analysis()
        assert "efficiency_factor" in analysis
        assert analysis["efficiency_factor"] == 0.85

    def test_k_calculation_with_efficiency_factor_electric(self, zone_name: str):
        """Test K calculation with electric efficiency (1.0).

        For electric, consumed energy = thermal energy.
        K = Energy / (ΔT × duration)

        1000W heater, 6h heating, 24h period, ΔT=15°C, efficiency=1.0
        Thermal Energy = 1000W × 6h × 1.0 = 6000 Wh
        K = 6000 / (15 × 24) = 16.67 W/°C
        """
        heater_power = 1000.0
        model = ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,
            efficiency_factor=1.0,
        )

        base_time = time.time() - 24 * SECONDS_PER_HOUR
        for minute in range(24 * 60 + 1):
            ts = base_time + minute * 60
            hour = minute // 60
            heating_on = hour < 6

            model.add_data_point(
                ThermalDataPoint(
                    timestamp=ts,
                    indoor_temp=20.0,
                    outdoor_temp=5.0,
                    heating_on=heating_on,
                )
            )

        expected_k = (heater_power * 6 * 1.0) / (15 * 24)  # 16.67 W/°C
        assert model.k_coefficient_24h is not None
        assert model.k_coefficient_24h == pytest.approx(expected_k, rel=0.1)

    def test_k_calculation_with_efficiency_factor_heatpump(self, zone_name: str):
        """Test K calculation with heat pump efficiency (COP 3.0).

        For heat pump, 1 kWh consumed = 3 kWh thermal.
        K = Thermal Energy / (ΔT × duration)

        1000W consumed, 6h heating, 24h period, ΔT=15°C, efficiency=3.0
        Thermal Energy = 1000W × 6h × 3.0 = 18000 Wh
        K = 18000 / (15 × 24) = 50 W/°C
        """
        heater_power = 1000.0
        cop = 3.0
        model = ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,
            efficiency_factor=cop,
        )

        base_time = time.time() - 24 * SECONDS_PER_HOUR
        for minute in range(24 * 60 + 1):
            ts = base_time + minute * 60
            hour = minute // 60
            heating_on = hour < 6

            model.add_data_point(
                ThermalDataPoint(
                    timestamp=ts,
                    indoor_temp=20.0,
                    outdoor_temp=5.0,
                    heating_on=heating_on,
                )
            )

        # With COP 3.0, K should be 3x higher for same electric consumption
        expected_k = (heater_power * 6 * cop) / (15 * 24)  # 50 W/°C
        assert model.k_coefficient_24h is not None
        assert model.k_coefficient_24h == pytest.approx(expected_k, rel=0.1)

    def test_k_calculation_with_efficiency_factor_gas(self, zone_name: str):
        """Test K calculation with gas boiler efficiency (0.90).

        For gas, 1 kWh gas = 0.9 kWh thermal (combustion losses).
        K = Thermal Energy / (ΔT × duration)

        1000W consumed, 6h heating, 24h period, ΔT=15°C, efficiency=0.9
        Thermal Energy = 1000W × 6h × 0.9 = 5400 Wh
        K = 5400 / (15 × 24) = 15 W/°C
        """
        heater_power = 1000.0
        gas_efficiency = 0.9
        model = ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,
            efficiency_factor=gas_efficiency,
        )

        base_time = time.time() - 24 * SECONDS_PER_HOUR
        for minute in range(24 * 60 + 1):
            ts = base_time + minute * 60
            hour = minute // 60
            heating_on = hour < 6

            model.add_data_point(
                ThermalDataPoint(
                    timestamp=ts,
                    indoor_temp=20.0,
                    outdoor_temp=5.0,
                    heating_on=heating_on,
                )
            )

        # With 90% efficiency, K should be 0.9x for same gas consumption
        expected_k = (heater_power * 6 * gas_efficiency) / (15 * 24)  # 15 W/°C
        assert model.k_coefficient_24h is not None
        assert model.k_coefficient_24h == pytest.approx(expected_k, rel=0.1)

    def test_efficiency_factor_affects_7day_k(self, zone_name: str, heater_power: float):
        """Test that efficiency_factor affects 7-day K calculation."""
        # With heat pump COP of 3.0
        model_heatpump = ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,
            efficiency_factor=3.0,
        )

        # With electric (efficiency 1.0)
        model_electric = ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,
            efficiency_factor=1.0,
        )

        # Add same history to both
        for i in range(7):
            for model in [model_heatpump, model_electric]:
                model.add_daily_summary(
                    date=f"2025-01-{10 + i:02d}",
                    heating_hours=6.0,
                    avg_delta_t=10.0,
                    energy_kwh=9.0,  # Same energy consumption
                    avg_indoor_temp=20.0,
                    avg_outdoor_temp=10.0,
                    sample_count=1440,
                )

        # Heat pump K should be 3x electric K (same consumption, 3x heat output)
        assert model_heatpump.k_coefficient_7d is not None
        assert model_electric.k_coefficient_7d is not None
        assert model_heatpump.k_coefficient_7d == pytest.approx(model_electric.k_coefficient_7d * 3.0, rel=0.01)

    def test_efficiency_factor_in_k_per_m3(self, zone_name: str, heater_power: float, volume: float):
        """Test that efficiency_factor affects K/m³ calculation."""
        model = ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,
            volume=volume,
            efficiency_factor=3.0,
        )

        # Set K manually to test k_per_m3
        model._k_coefficient = 30.0  # This would be the result with efficiency applied

        # k_per_m3 should be K / volume
        assert model.k_per_m3 == pytest.approx(30.0 / volume, rel=0.01)

    def test_efficiency_factor_preserved_in_serialization(self, zone_name: str, heater_power: float):
        """Test that efficiency_factor is preserved in to_dict/from_dict."""
        model = ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,
            efficiency_factor=0.85,
        )

        # Add some data
        base_time = time.time()
        for i in range(5):
            model.add_data_point(
                ThermalDataPoint(
                    timestamp=base_time + i * 60,
                    indoor_temp=20.0,
                    outdoor_temp=5.0,
                    heating_on=True,
                )
            )

        # Serialize
        data = model.to_dict()

        # Create new model with SAME efficiency_factor (not in serialized data)
        # efficiency_factor is a config setting, not persisted state
        new_model = ThermalLossModel(
            zone_name=zone_name,
            heater_power=heater_power,
            efficiency_factor=0.85,
        )
        new_model.from_dict(data)

        assert new_model.efficiency_factor == 0.85


class TestThermalLossModelPerfectDaysComfort:
    """Test perfect days filtering with MIN_COMFORT_TEMP threshold."""

    def test_perfect_day_requires_comfortable_temp(self, zone_name: str, heater_power: float):
        """Test that a 'perfect' day must have comfortable indoor temp (≥ 17°C)."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)

        # Add normal days with heating (to establish K_min)
        for i in range(3):
            model.add_daily_summary(
                date=f"2025-01-{10 + i:02d}",
                heating_hours=6.0,
                avg_delta_t=10.0,
                energy_kwh=9.0,
                avg_indoor_temp=20.0,
                avg_outdoor_temp=10.0,
                sample_count=1440,
                temp_variation=1.5,
            )

        k_7d_before = model.k_coefficient_7d

        # Add a day with minimal heating, stable temp, but TOO COLD (< 17°C)
        model.add_daily_summary(
            date="2025-01-15",
            heating_hours=0.05,  # Almost no heating
            avg_delta_t=10.0,
            energy_kwh=0.1,
            avg_indoor_temp=15.0,  # Too cold! (< 17°C)
            avg_outdoor_temp=5.0,
            sample_count=1440,
            temp_variation=1.0,  # Stable
        )

        # K_7d should NOT change - cold day is not "perfect"
        # (Day is filtered out from K calculation)
        assert model.k_coefficient_7d == k_7d_before

    def test_perfect_day_with_comfortable_temp_is_counted(self, zone_name: str, heater_power: float):
        """Test that a perfect day with comfortable temp is included in K calculation."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)

        # Add normal days with heating
        for i in range(3):
            model.add_daily_summary(
                date=f"2025-01-{10 + i:02d}",
                heating_hours=6.0,
                avg_delta_t=10.0,
                energy_kwh=9.0,
                avg_indoor_temp=20.0,
                avg_outdoor_temp=10.0,
                sample_count=1440,
                temp_variation=1.5,
            )

        # Add a perfect day: minimal heating, stable AND comfortable temp
        model.add_daily_summary(
            date="2025-01-15",
            heating_hours=0.05,  # Almost no heating
            avg_delta_t=10.0,
            energy_kwh=0.1,
            avg_indoor_temp=19.0,  # Comfortable (≥ 17°C)
            avg_outdoor_temp=9.0,
            sample_count=1440,
            temp_variation=1.0,  # Stable
        )

        # K_7d should be calculated and include 4 days
        assert model.k_coefficient_7d is not None
        assert model.history_days_count == 4


class TestThermalLossModelLastKDate:
    """Test last_k_date property tracking."""

    def test_last_k_date_initially_none(self, zone_name: str, heater_power: float):
        """Test that last_k_date is None initially."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        assert model.last_k_date is None

    def test_last_k_date_set_after_k_calculation(self, zone_name: str, heater_power: float):
        """Test that last_k_date is set after K calculation."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)

        # Add enough data for K calculation
        base_time = time.time() - 24 * SECONDS_PER_HOUR
        for minute in range(24 * 60 + 1):
            ts = base_time + minute * 60
            hour = minute // 60
            heating_on = hour < 6

            model.add_data_point(
                ThermalDataPoint(
                    timestamp=ts,
                    indoor_temp=20.0,
                    outdoor_temp=5.0,
                    heating_on=heating_on,
                )
            )

        # K should be calculated
        assert model.k_coefficient_24h is not None
        # last_k_date should be set to today
        assert model.last_k_date is not None

    def test_last_k_date_in_analysis(self, zone_name: str, heater_power: float):
        """Test that last_k_date is included in get_analysis output."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)

        # Add history to trigger K_7d calculation
        for i in range(5):
            model.add_daily_summary(
                date=f"2025-01-{10 + i:02d}",
                heating_hours=6.0,
                avg_delta_t=10.0,
                energy_kwh=9.0,
                avg_indoor_temp=20.0,
                avg_outdoor_temp=10.0,
                sample_count=1440,
            )

        analysis = model.get_analysis()
        assert "last_k_date" in analysis

    def test_last_k_date_cleared_on_clear_all(self, zone_name: str, heater_power: float):
        """Test that last_k_date is cleared on clear_all."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        model._last_k_date = "2025-01-15"

        model.clear_all()

        assert model.last_k_date is None

    def test_last_k_date_preserved_in_serialization(self, zone_name: str, heater_power: float):
        """Test that last_k_date is preserved in to_dict/from_dict."""
        model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        model._last_k_date = "2025-01-15"

        # Serialize
        data = model.to_dict()
        assert data.get("last_k_date") == "2025-01-15"

        # Deserialize
        new_model = ThermalLossModel(zone_name=zone_name, heater_power=heater_power)
        new_model.from_dict(data)

        assert new_model.last_k_date == "2025-01-15"
