"""Fixtures for Home Performance tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def zone_name() -> str:
    """Return a test zone name."""
    return "Salon"


@pytest.fixture
def heater_power() -> float:
    """Return a test heater power in Watts."""
    return 1500.0


@pytest.fixture
def surface() -> float:
    """Return a test surface in m²."""
    return 20.0


@pytest.fixture
def volume() -> float:
    """Return a test volume in m³."""
    return 50.0
