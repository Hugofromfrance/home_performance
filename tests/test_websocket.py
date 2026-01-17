"""Tests for Home Performance WebSocket commands."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.home_performance import websocket_get_version
from custom_components.home_performance.const import DOMAIN, VERSION


class TestWebsocketGetVersion:
    """Test websocket_get_version command."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock hass object."""
        return MagicMock()

    @pytest.fixture
    def mock_connection(self):
        """Create a mock WebSocket connection."""
        connection = MagicMock()
        connection.send_result = MagicMock()
        return connection

    def test_returns_version(self, mock_hass, mock_connection):
        """Test that websocket_get_version returns the integration version."""
        msg = {"id": 1, "type": f"{DOMAIN}/version"}

        websocket_get_version(mock_hass, mock_connection, msg)

        mock_connection.send_result.assert_called_once_with(
            1,
            {"version": VERSION},
        )

    def test_uses_message_id(self, mock_hass, mock_connection):
        """Test that websocket_get_version uses the correct message ID."""
        msg = {"id": 42, "type": f"{DOMAIN}/version"}

        websocket_get_version(mock_hass, mock_connection, msg)

        call_args = mock_connection.send_result.call_args
        assert call_args[0][0] == 42

    def test_version_is_string(self, mock_hass, mock_connection):
        """Test that returned version is a string."""
        msg = {"id": 1, "type": f"{DOMAIN}/version"}

        websocket_get_version(mock_hass, mock_connection, msg)

        call_args = mock_connection.send_result.call_args
        result = call_args[0][1]
        assert isinstance(result["version"], str)

    def test_version_not_empty(self, mock_hass, mock_connection):
        """Test that returned version is not empty."""
        msg = {"id": 1, "type": f"{DOMAIN}/version"}

        websocket_get_version(mock_hass, mock_connection, msg)

        call_args = mock_connection.send_result.call_args
        result = call_args[0][1]
        assert len(result["version"]) > 0

    def test_version_matches_const(self, mock_hass, mock_connection):
        """Test that returned version matches VERSION constant."""
        msg = {"id": 1, "type": f"{DOMAIN}/version"}

        websocket_get_version(mock_hass, mock_connection, msg)

        call_args = mock_connection.send_result.call_args
        result = call_args[0][1]
        assert result["version"] == VERSION
