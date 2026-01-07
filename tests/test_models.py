"""Tests for Home Performance models."""

from __future__ import annotations

import time

import pytest

from custom_components.home_performance.models import (
    SEASON_HEATING,
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
