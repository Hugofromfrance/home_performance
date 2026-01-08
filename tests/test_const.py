"""Tests for Home Performance constants."""

from __future__ import annotations

import json
from unittest.mock import mock_open, patch

from custom_components.home_performance.const import (
    AGGREGATION_PERIOD_HOURS,
    BINARY_SENSOR_ENTITY_SUFFIXES,
    DEFAULT_POWER_THRESHOLD,
    DOMAIN,
    HISTORY_DAYS,
    MIN_DATA_HOURS,
    MIN_DELTA_T,
    MIN_HEATING_TIME_HOURS,
    ORIENTATIONS,
    SENSOR_ENTITY_SUFFIXES,
    VERSION,
    get_version,
)


class TestDomainConstant:
    """Test domain constant."""

    def test_domain_is_string(self):
        """Test that DOMAIN is a non-empty string."""
        assert isinstance(DOMAIN, str)
        assert len(DOMAIN) > 0

    def test_domain_value(self):
        """Test domain has expected value."""
        assert DOMAIN == "home_performance"


class TestEntitySuffixes:
    """Test entity ID suffix mappings."""

    def test_sensor_suffixes_is_dict(self):
        """Test that SENSOR_ENTITY_SUFFIXES is a dictionary."""
        assert isinstance(SENSOR_ENTITY_SUFFIXES, dict)

    def test_sensor_suffixes_not_empty(self):
        """Test that SENSOR_ENTITY_SUFFIXES has entries."""
        assert len(SENSOR_ENTITY_SUFFIXES) > 0

    def test_sensor_suffixes_all_strings(self):
        """Test that all keys and values in SENSOR_ENTITY_SUFFIXES are strings."""
        for key, value in SENSOR_ENTITY_SUFFIXES.items():
            assert isinstance(key, str), f"Key {key} is not a string"
            assert isinstance(value, str), f"Value {value} for key {key} is not a string"

    def test_sensor_suffixes_no_spaces(self):
        """Test that entity suffixes don't contain spaces (would break entity_id)."""
        for key, value in SENSOR_ENTITY_SUFFIXES.items():
            assert " " not in key, f"Key '{key}' contains spaces"
            assert " " not in value, f"Value '{value}' for key '{key}' contains spaces"

    def test_sensor_suffixes_lowercase(self):
        """Test that entity suffixes are lowercase (HA convention)."""
        for key, value in SENSOR_ENTITY_SUFFIXES.items():
            assert key == key.lower(), f"Key '{key}' is not lowercase"
            assert value == value.lower(), f"Value '{value}' is not lowercase"

    def test_expected_sensor_types_present(self):
        """Test that expected sensor types are present in mapping."""
        expected_types = [
            "k_coefficient",
            "k_per_m2",
            "k_per_m3",
            "daily_energy",
            "heating_time",
            "heating_ratio",
            "energy_performance",
            "avg_delta_t",
            "data_hours",
            "analysis_remaining",
            "analysis_progress",
            "insulation_rating",
            "measured_energy_daily",
        ]
        for sensor_type in expected_types:
            assert sensor_type in SENSOR_ENTITY_SUFFIXES, f"Missing sensor type: {sensor_type}"

    def test_binary_sensor_suffixes_is_dict(self):
        """Test that BINARY_SENSOR_ENTITY_SUFFIXES is a dictionary."""
        assert isinstance(BINARY_SENSOR_ENTITY_SUFFIXES, dict)

    def test_binary_sensor_suffixes_not_empty(self):
        """Test that BINARY_SENSOR_ENTITY_SUFFIXES has entries."""
        assert len(BINARY_SENSOR_ENTITY_SUFFIXES) > 0

    def test_expected_binary_sensor_types_present(self):
        """Test that expected binary sensor types are present in mapping."""
        expected_types = ["window_open", "heating_active", "data_ready"]
        for sensor_type in expected_types:
            assert sensor_type in BINARY_SENSOR_ENTITY_SUFFIXES, f"Missing binary sensor type: {sensor_type}"

    def test_binary_sensor_suffixes_no_spaces(self):
        """Test that binary sensor suffixes don't contain spaces."""
        for key, value in BINARY_SENSOR_ENTITY_SUFFIXES.items():
            assert " " not in key, f"Key '{key}' contains spaces"
            assert " " not in value, f"Value '{value}' for key '{key}' contains spaces"


class TestThresholdConstants:
    """Test threshold constants have sensible values."""

    def test_min_delta_t_positive(self):
        """Test MIN_DELTA_T is positive."""
        assert MIN_DELTA_T > 0
        assert MIN_DELTA_T == 5.0  # Expected value for reliable K calculation

    def test_min_data_hours_positive(self):
        """Test MIN_DATA_HOURS is positive."""
        assert MIN_DATA_HOURS > 0
        assert MIN_DATA_HOURS == 12  # Expected minimum hours for first calculation

    def test_min_heating_time_positive(self):
        """Test MIN_HEATING_TIME_HOURS is positive."""
        assert MIN_HEATING_TIME_HOURS > 0
        assert MIN_HEATING_TIME_HOURS == 0.5  # 30 minutes minimum

    def test_history_days_sensible(self):
        """Test HISTORY_DAYS is sensible."""
        assert HISTORY_DAYS >= 1
        assert HISTORY_DAYS == 7  # 7-day rolling average

    def test_aggregation_period_hours(self):
        """Test AGGREGATION_PERIOD_HOURS is 24h."""
        assert AGGREGATION_PERIOD_HOURS == 24

    def test_default_power_threshold(self):
        """Test DEFAULT_POWER_THRESHOLD is sensible."""
        assert DEFAULT_POWER_THRESHOLD > 0
        assert DEFAULT_POWER_THRESHOLD == 50  # 50W threshold


class TestOrientations:
    """Test room orientations constant."""

    def test_orientations_is_list(self):
        """Test ORIENTATIONS is a list."""
        assert isinstance(ORIENTATIONS, list)

    def test_orientations_has_8_directions(self):
        """Test ORIENTATIONS has 8 cardinal/intercardinal directions."""
        assert len(ORIENTATIONS) == 8

    def test_orientations_contains_expected(self):
        """Test ORIENTATIONS contains expected directions."""
        expected = ["n", "ne", "e", "se", "s", "sw", "w", "nw"]
        assert set(ORIENTATIONS) == set(expected)


class TestGetVersion:
    """Test get_version function."""

    def test_version_is_string(self):
        """Test that VERSION is a string."""
        assert isinstance(VERSION, str)

    def test_version_not_empty(self):
        """Test that VERSION is not empty or unknown in normal case."""
        # In normal operation, version should be read from manifest.json
        assert VERSION != ""

    def test_get_version_returns_string(self):
        """Test get_version returns a string."""
        result = get_version()
        assert isinstance(result, str)

    def test_get_version_file_not_found(self):
        """Test get_version returns 'unknown' when manifest.json not found."""
        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = get_version()
            assert result == "unknown"

    def test_get_version_invalid_json(self):
        """Test get_version returns 'unknown' when manifest.json is invalid."""
        with patch("builtins.open", mock_open(read_data="invalid json {")):
            result = get_version()
            assert result == "unknown"

    def test_get_version_missing_version_key(self):
        """Test get_version returns 'unknown' when version key is missing."""
        manifest_without_version = json.dumps({"domain": "test"})
        with patch("builtins.open", mock_open(read_data=manifest_without_version)):
            result = get_version()
            assert result == "unknown"

    def test_get_version_valid_manifest(self):
        """Test get_version returns version from valid manifest."""
        manifest_data = json.dumps({"version": "1.2.3", "domain": "test"})
        with patch("builtins.open", mock_open(read_data=manifest_data)):
            result = get_version()
            assert result == "1.2.3"
