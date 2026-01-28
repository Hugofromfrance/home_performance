"""Tests for Home Performance constants."""

from __future__ import annotations

import json
from unittest.mock import mock_open, patch

from custom_components.home_performance.const import (
    AGGREGATION_PERIOD_HOURS,
    BINARY_SENSOR_ENTITY_SUFFIXES,
    DEFAULT_EFFICIENCY_FACTORS,
    DEFAULT_HEAT_SOURCE_TYPE,
    DEFAULT_POWER_THRESHOLD,
    DOMAIN,
    HEAT_SOURCE_ELECTRIC,
    HEAT_SOURCE_GAS,
    HEAT_SOURCE_GAS_BOILER,
    HEAT_SOURCE_GAS_FURNACE,
    HEAT_SOURCE_HEATPUMP,
    HEAT_SOURCE_MIGRATION,
    HEAT_SOURCE_TYPES,
    HEAT_SOURCES_REQUIRING_ENERGY,
    HISTORY_DAYS,
    JSMODULES,
    MIN_DATA_HOURS,
    MIN_DELTA_T,
    MIN_HEATING_TIME_HOURS,
    ORIENTATIONS,
    SENSOR_ENTITY_SUFFIXES,
    URL_BASE,
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

    def test_orientations_are_lowercase(self):
        """Test ORIENTATIONS are all lowercase for case-insensitive matching.

        This is important for backward compatibility with legacy data
        that may have been stored in uppercase (e.g., "N" instead of "n").
        The config_flow and coordinator normalize values to lowercase.
        """
        for orientation in ORIENTATIONS:
            assert orientation == orientation.lower()
            assert orientation.isalpha() or orientation.isalnum()

    def test_legacy_uppercase_can_be_normalized(self):
        """Test that uppercase legacy values can be normalized to match ORIENTATIONS."""
        legacy_values = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        for legacy in legacy_values:
            normalized = legacy.lower()
            assert normalized in ORIENTATIONS, f"{legacy} should normalize to a valid orientation"


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


class TestFrontendConstants:
    """Test frontend-related constants."""

    def test_url_base_is_string(self):
        """Test that URL_BASE is a non-empty string."""
        assert isinstance(URL_BASE, str)
        assert len(URL_BASE) > 0

    def test_url_base_starts_with_slash(self):
        """Test that URL_BASE starts with / for valid HTTP path."""
        assert URL_BASE.startswith("/")

    def test_url_base_no_trailing_slash(self):
        """Test that URL_BASE has no trailing slash."""
        assert not URL_BASE.endswith("/")

    def test_url_base_value(self):
        """Test URL_BASE has expected value."""
        assert URL_BASE == "/home-performance"

    def test_jsmodules_is_list(self):
        """Test that JSMODULES is a list."""
        assert isinstance(JSMODULES, list)

    def test_jsmodules_not_empty(self):
        """Test that JSMODULES has at least one module."""
        assert len(JSMODULES) > 0

    def test_jsmodules_structure(self):
        """Test that each module in JSMODULES has required keys."""
        required_keys = {"name", "filename", "version"}
        for module in JSMODULES:
            assert isinstance(module, dict)
            assert required_keys.issubset(module.keys()), f"Module missing keys: {required_keys - module.keys()}"

    def test_jsmodules_filename_is_js(self):
        """Test that module filenames end with .js."""
        for module in JSMODULES:
            assert module["filename"].endswith(".js"), f"Filename {module['filename']} should end with .js"

    def test_jsmodules_version_matches_integration(self):
        """Test that module version matches integration VERSION."""
        for module in JSMODULES:
            assert module["version"] == VERSION, f"Module version {module['version']} != integration VERSION {VERSION}"

    def test_jsmodules_contains_main_card(self):
        """Test that JSMODULES contains the main card."""
        filenames = [m["filename"] for m in JSMODULES]
        assert "home-performance-card.js" in filenames


class TestHeatSourceTypes:
    """Test heat source type constants."""

    def test_heat_source_electric_value(self):
        """Test HEAT_SOURCE_ELECTRIC constant value."""
        assert HEAT_SOURCE_ELECTRIC == "electric"

    def test_heat_source_heatpump_value(self):
        """Test HEAT_SOURCE_HEATPUMP constant value."""
        assert HEAT_SOURCE_HEATPUMP == "heatpump"

    def test_heat_source_gas_boiler_value(self):
        """Test HEAT_SOURCE_GAS_BOILER constant value."""
        assert HEAT_SOURCE_GAS_BOILER == "gas_boiler"

    def test_heat_source_gas_furnace_value(self):
        """Test HEAT_SOURCE_GAS_FURNACE constant value."""
        assert HEAT_SOURCE_GAS_FURNACE == "gas_furnace"

    def test_heat_source_gas_legacy_value(self):
        """Test HEAT_SOURCE_GAS legacy constant value."""
        assert HEAT_SOURCE_GAS == "gas"

    def test_heat_source_types_list(self):
        """Test HEAT_SOURCE_TYPES contains all current types."""
        assert HEAT_SOURCE_ELECTRIC in HEAT_SOURCE_TYPES
        assert HEAT_SOURCE_HEATPUMP in HEAT_SOURCE_TYPES
        assert HEAT_SOURCE_GAS_BOILER in HEAT_SOURCE_TYPES
        assert HEAT_SOURCE_GAS_FURNACE in HEAT_SOURCE_TYPES
        # Legacy type should NOT be in current types
        assert HEAT_SOURCE_GAS not in HEAT_SOURCE_TYPES

    def test_heat_sources_requiring_energy(self):
        """Test HEAT_SOURCES_REQUIRING_ENERGY list."""
        # Electric should NOT require energy sensor (uses heater_power)
        assert HEAT_SOURCE_ELECTRIC not in HEAT_SOURCES_REQUIRING_ENERGY
        # Non-electric sources benefit from energy sensor
        assert HEAT_SOURCE_HEATPUMP in HEAT_SOURCES_REQUIRING_ENERGY
        assert HEAT_SOURCE_GAS_BOILER in HEAT_SOURCES_REQUIRING_ENERGY
        assert HEAT_SOURCE_GAS_FURNACE in HEAT_SOURCES_REQUIRING_ENERGY

    def test_default_heat_source_type(self):
        """Test default heat source is electric."""
        assert DEFAULT_HEAT_SOURCE_TYPE == HEAT_SOURCE_ELECTRIC


class TestHeatSourceMigration:
    """Test heat source migration constants."""

    def test_migration_mapping_exists(self):
        """Test HEAT_SOURCE_MIGRATION is a dict."""
        assert isinstance(HEAT_SOURCE_MIGRATION, dict)

    def test_legacy_gas_maps_to_gas_boiler(self):
        """Test legacy 'gas' type maps to 'gas_boiler'."""
        assert HEAT_SOURCE_GAS in HEAT_SOURCE_MIGRATION
        assert HEAT_SOURCE_MIGRATION[HEAT_SOURCE_GAS] == HEAT_SOURCE_GAS_BOILER

    def test_migration_only_contains_legacy_types(self):
        """Test migration dict only contains legacy types."""
        for legacy_type in HEAT_SOURCE_MIGRATION.keys():
            # Legacy types should NOT be in current HEAT_SOURCE_TYPES
            assert legacy_type not in HEAT_SOURCE_TYPES


class TestEfficiencyFactors:
    """Test efficiency factor constants."""

    def test_default_efficiency_factors_is_dict(self):
        """Test DEFAULT_EFFICIENCY_FACTORS is a dictionary."""
        assert isinstance(DEFAULT_EFFICIENCY_FACTORS, dict)

    def test_electric_efficiency_is_1(self):
        """Test electric efficiency factor is 1.0 (100% efficient)."""
        assert DEFAULT_EFFICIENCY_FACTORS[HEAT_SOURCE_ELECTRIC] == 1.0

    def test_heatpump_efficiency_is_cop(self):
        """Test heat pump efficiency factor represents typical COP."""
        # Heat pump COP typically 2.5-4.0
        cop = DEFAULT_EFFICIENCY_FACTORS[HEAT_SOURCE_HEATPUMP]
        assert 2.0 <= cop <= 5.0
        assert cop == 3.0  # Expected default

    def test_gas_boiler_efficiency_less_than_1(self):
        """Test gas boiler efficiency is less than 1.0 (combustion losses)."""
        efficiency = DEFAULT_EFFICIENCY_FACTORS[HEAT_SOURCE_GAS_BOILER]
        assert 0.8 <= efficiency <= 1.0
        assert efficiency == 0.90  # Expected for condensing boilers

    def test_gas_furnace_efficiency_lower_than_boiler(self):
        """Test gas furnace efficiency is lower than boiler (distribution losses)."""
        furnace_eff = DEFAULT_EFFICIENCY_FACTORS[HEAT_SOURCE_GAS_FURNACE]
        boiler_eff = DEFAULT_EFFICIENCY_FACTORS[HEAT_SOURCE_GAS_BOILER]
        assert furnace_eff < boiler_eff
        assert furnace_eff == 0.85  # Expected for US furnaces

    def test_legacy_gas_has_efficiency(self):
        """Test legacy gas type has efficiency factor for backward compat."""
        assert HEAT_SOURCE_GAS in DEFAULT_EFFICIENCY_FACTORS
        # Should match gas_boiler
        assert DEFAULT_EFFICIENCY_FACTORS[HEAT_SOURCE_GAS] == DEFAULT_EFFICIENCY_FACTORS[HEAT_SOURCE_GAS_BOILER]

    def test_all_heat_source_types_have_efficiency(self):
        """Test all heat source types have an efficiency factor."""
        for heat_source in HEAT_SOURCE_TYPES:
            assert heat_source in DEFAULT_EFFICIENCY_FACTORS, f"Missing efficiency for {heat_source}"

    def test_efficiency_factors_are_positive(self):
        """Test all efficiency factors are positive numbers."""
        for heat_source, efficiency in DEFAULT_EFFICIENCY_FACTORS.items():
            assert isinstance(efficiency, (int, float)), f"Efficiency for {heat_source} is not a number"
            assert efficiency > 0, f"Efficiency for {heat_source} must be positive"
