"""Tests for Home Performance frontend module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.home_performance.const import URL_BASE, VERSION
from custom_components.home_performance.frontend import WWW_PATH, JSModuleRegistration


class TestWWWPath:
    """Test WWW_PATH constant."""

    def test_www_path_is_path(self):
        """Test that WWW_PATH is a Path object."""
        assert isinstance(WWW_PATH, Path)

    def test_www_path_ends_with_www(self):
        """Test that WWW_PATH points to www directory."""
        assert WWW_PATH.name == "www"

    def test_www_path_exists(self):
        """Test that WWW_PATH directory exists."""
        assert WWW_PATH.exists()
        assert WWW_PATH.is_dir()

    def test_www_path_contains_card_js(self):
        """Test that WWW_PATH contains the card JavaScript file."""
        card_file = WWW_PATH / "home-performance-card.js"
        assert card_file.exists()


class TestJSModuleRegistrationInit:
    """Test JSModuleRegistration initialization."""

    def test_init_stores_hass(self):
        """Test that __init__ stores hass reference."""
        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": MagicMock()}

        registration = JSModuleRegistration(mock_hass)

        assert registration.hass is mock_hass

    def test_init_gets_lovelace_from_hass_data(self):
        """Test that __init__ retrieves lovelace from hass.data."""
        mock_lovelace = MagicMock()
        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}

        registration = JSModuleRegistration(mock_hass)

        assert registration.lovelace is mock_lovelace

    def test_init_handles_missing_lovelace(self):
        """Test that __init__ handles missing lovelace gracefully."""
        mock_hass = MagicMock()
        mock_hass.data = {}

        registration = JSModuleRegistration(mock_hass)

        assert registration.lovelace is None


class TestJSModuleRegistrationHelpers:
    """Test JSModuleRegistration helper methods."""

    def test_get_path_without_query(self):
        """Test _get_path returns URL without query string."""
        result = JSModuleRegistration._get_path("/home-performance/card.js")
        assert result == "/home-performance/card.js"

    def test_get_path_with_query(self):
        """Test _get_path strips query string from URL."""
        result = JSModuleRegistration._get_path("/home-performance/card.js?v=1.2.3")
        assert result == "/home-performance/card.js"

    def test_get_path_with_multiple_query_params(self):
        """Test _get_path handles multiple query parameters."""
        result = JSModuleRegistration._get_path("/path/file.js?v=1.0&cache=false")
        assert result == "/path/file.js"

    def test_get_version_with_version_param(self):
        """Test _get_version extracts version from URL."""
        result = JSModuleRegistration._get_version("/path/file.js?v=1.2.3")
        assert result == "1.2.3"

    def test_get_version_without_version_param(self):
        """Test _get_version returns None when no version."""
        result = JSModuleRegistration._get_version("/path/file.js")
        assert result is None

    def test_get_version_empty_version(self):
        """Test _get_version with empty version parameter."""
        result = JSModuleRegistration._get_version("/path/file.js?v=")
        assert result == ""


class TestJSModuleRegistrationRegisterPath:
    """Test JSModuleRegistration._async_register_path method."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock hass object."""
        mock = MagicMock()
        mock.data = {"lovelace": MagicMock()}
        mock.http.async_register_static_paths = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_register_path_calls_http_register(self, mock_hass):
        """Test that _async_register_path registers static path."""
        registration = JSModuleRegistration(mock_hass)

        await registration._async_register_path()

        mock_hass.http.async_register_static_paths.assert_called_once()
        call_args = mock_hass.http.async_register_static_paths.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0].url_path == URL_BASE

    @pytest.mark.asyncio
    async def test_register_path_handles_runtime_error(self, mock_hass):
        """Test that _async_register_path handles already registered path."""
        mock_hass.http.async_register_static_paths = AsyncMock(
            side_effect=RuntimeError("Path already registered")
        )
        registration = JSModuleRegistration(mock_hass)

        # Should not raise
        await registration._async_register_path()


class TestJSModuleRegistrationRegister:
    """Test JSModuleRegistration.async_register method."""

    @pytest.fixture
    def mock_hass_storage_mode(self):
        """Create a mock hass with lovelace in storage mode."""
        mock_lovelace = MagicMock()
        mock_lovelace.mode = "storage"
        mock_lovelace.resources.loaded = True
        mock_lovelace.resources.async_items = MagicMock(return_value=[])
        mock_lovelace.resources.async_create_item = AsyncMock()

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}
        mock_hass.http.async_register_static_paths = AsyncMock()
        return mock_hass

    @pytest.fixture
    def mock_hass_yaml_mode(self):
        """Create a mock hass with lovelace in YAML mode."""
        mock_lovelace = MagicMock()
        mock_lovelace.mode = "yaml"

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}
        mock_hass.http.async_register_static_paths = AsyncMock()
        return mock_hass

    @pytest.mark.asyncio
    async def test_register_in_storage_mode(self, mock_hass_storage_mode):
        """Test async_register in storage mode registers resources."""
        registration = JSModuleRegistration(mock_hass_storage_mode)

        await registration.async_register()

        # Should register static path
        mock_hass_storage_mode.http.async_register_static_paths.assert_called_once()
        # Should register resources
        mock_hass_storage_mode.data["lovelace"].resources.async_create_item.assert_called()

    @pytest.mark.asyncio
    async def test_register_in_yaml_mode(self, mock_hass_yaml_mode):
        """Test async_register in YAML mode only registers static path."""
        registration = JSModuleRegistration(mock_hass_yaml_mode)

        await registration.async_register()

        # Should register static path
        mock_hass_yaml_mode.http.async_register_static_paths.assert_called_once()
        # Should NOT try to register Lovelace resources
        assert not hasattr(mock_hass_yaml_mode.data["lovelace"].resources, "async_create_item") or \
               not mock_hass_yaml_mode.data["lovelace"].resources.async_create_item.called

    @pytest.mark.asyncio
    async def test_register_without_lovelace(self):
        """Test async_register when lovelace is not available."""
        mock_hass = MagicMock()
        mock_hass.data = {}
        mock_hass.http.async_register_static_paths = AsyncMock()

        registration = JSModuleRegistration(mock_hass)

        # Should not raise
        await registration.async_register()

        # Should still register static path
        mock_hass.http.async_register_static_paths.assert_called_once()


class TestJSModuleRegistrationRegisterModules:
    """Test JSModuleRegistration._async_register_modules method."""

    @pytest.fixture
    def mock_hass_with_lovelace(self):
        """Create a mock hass with lovelace resources."""
        mock_lovelace = MagicMock()
        mock_lovelace.mode = "storage"
        mock_lovelace.resources.loaded = True
        mock_lovelace.resources.async_items = MagicMock(return_value=[])
        mock_lovelace.resources.async_create_item = AsyncMock()
        mock_lovelace.resources.async_update_item = AsyncMock()

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}
        mock_hass.http.async_register_static_paths = AsyncMock()
        return mock_hass

    @pytest.mark.asyncio
    async def test_register_new_module(self, mock_hass_with_lovelace):
        """Test registering a new module."""
        registration = JSModuleRegistration(mock_hass_with_lovelace)

        await registration._async_register_modules()

        # Should create new resource
        mock_hass_with_lovelace.data["lovelace"].resources.async_create_item.assert_called()
        call_args = mock_hass_with_lovelace.data["lovelace"].resources.async_create_item.call_args[0][0]
        assert call_args["res_type"] == "module"
        assert URL_BASE in call_args["url"]
        assert f"?v={VERSION}" in call_args["url"]

    @pytest.mark.asyncio
    async def test_update_existing_module_different_version(self, mock_hass_with_lovelace):
        """Test updating an existing module with different version."""
        existing_resource = {
            "id": "test-id",
            "url": f"{URL_BASE}/home-performance-card.js?v=0.0.1",
        }
        mock_hass_with_lovelace.data["lovelace"].resources.async_items = MagicMock(
            return_value=[existing_resource]
        )

        registration = JSModuleRegistration(mock_hass_with_lovelace)

        await registration._async_register_modules()

        # Should update existing resource
        mock_hass_with_lovelace.data["lovelace"].resources.async_update_item.assert_called_once()
        call_args = mock_hass_with_lovelace.data["lovelace"].resources.async_update_item.call_args
        assert call_args[0][0] == "test-id"
        assert f"?v={VERSION}" in call_args[0][1]["url"]

    @pytest.mark.asyncio
    async def test_skip_update_same_version(self, mock_hass_with_lovelace):
        """Test skipping update when version matches."""
        existing_resource = {
            "id": "test-id",
            "url": f"{URL_BASE}/home-performance-card.js?v={VERSION}",
        }
        mock_hass_with_lovelace.data["lovelace"].resources.async_items = MagicMock(
            return_value=[existing_resource]
        )

        registration = JSModuleRegistration(mock_hass_with_lovelace)

        await registration._async_register_modules()

        # Should NOT update or create
        mock_hass_with_lovelace.data["lovelace"].resources.async_update_item.assert_not_called()
        mock_hass_with_lovelace.data["lovelace"].resources.async_create_item.assert_not_called()


class TestJSModuleRegistrationUnregister:
    """Test JSModuleRegistration.async_unregister method."""

    @pytest.mark.asyncio
    async def test_unregister_removes_resources(self):
        """Test async_unregister removes registered resources."""
        existing_resources = [
            {"id": "res-1", "url": f"{URL_BASE}/home-performance-card.js?v=1.0"},
        ]
        mock_lovelace = MagicMock()
        mock_lovelace.mode = "storage"
        mock_lovelace.resources.loaded = True
        mock_lovelace.resources.async_items = MagicMock(return_value=existing_resources)
        mock_lovelace.resources.async_delete_item = AsyncMock()

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}

        registration = JSModuleRegistration(mock_hass)

        await registration.async_unregister()

        mock_lovelace.resources.async_delete_item.assert_called_once_with("res-1")

    @pytest.mark.asyncio
    async def test_unregister_skips_yaml_mode(self):
        """Test async_unregister does nothing in YAML mode."""
        mock_lovelace = MagicMock()
        mock_lovelace.mode = "yaml"

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}

        registration = JSModuleRegistration(mock_hass)

        await registration.async_unregister()

        # Should not try to delete anything
        assert not hasattr(mock_lovelace.resources, "async_delete_item") or \
               not mock_lovelace.resources.async_delete_item.called

    @pytest.mark.asyncio
    async def test_unregister_skips_when_resources_not_loaded(self):
        """Test async_unregister does nothing when resources not loaded."""
        mock_lovelace = MagicMock()
        mock_lovelace.mode = "storage"
        mock_lovelace.resources.loaded = False

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}

        registration = JSModuleRegistration(mock_hass)

        await registration.async_unregister()

        # Should not try to delete anything
        mock_lovelace.resources.async_delete_item.assert_not_called()
