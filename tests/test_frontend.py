"""Tests for Home Performance frontend module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.home_performance.const import URL_BASE, VERSION
from custom_components.home_performance.frontend import LEGACY_URL_BASE, WWW_PATH, JSModuleRegistration


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


class TestConstants:
    """Test module-level constants."""

    def test_legacy_url_base_uses_underscore(self):
        """Test that LEGACY_URL_BASE uses underscore (matching old domain path)."""
        assert LEGACY_URL_BASE == "/home_performance"

    def test_url_base_uses_hyphen(self):
        """Test that URL_BASE uses hyphen."""
        assert URL_BASE == "/home-performance"

    def test_legacy_and_current_url_differ(self):
        """Test that legacy and current URL bases are different."""
        assert LEGACY_URL_BASE != URL_BASE


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
    async def test_register_path_registers_both_current_and_legacy(self, mock_hass):
        """Test that _async_register_path registers both /home-performance and /home_performance."""
        registration = JSModuleRegistration(mock_hass)

        await registration._async_register_path()

        assert mock_hass.http.async_register_static_paths.call_count == 2
        registered_paths = [
            call[0][0][0].url_path for call in mock_hass.http.async_register_static_paths.call_args_list
        ]
        assert URL_BASE in registered_paths
        assert LEGACY_URL_BASE in registered_paths

    @pytest.mark.asyncio
    async def test_register_path_handles_runtime_error(self, mock_hass):
        """Test that _async_register_path handles already registered path."""
        mock_hass.http.async_register_static_paths = AsyncMock(side_effect=RuntimeError("Path already registered"))
        registration = JSModuleRegistration(mock_hass)

        await registration._async_register_path()

    @pytest.mark.asyncio
    async def test_register_path_legacy_error_does_not_block_current(self, mock_hass):
        """Test that a RuntimeError on legacy path doesn't prevent current path registration."""
        call_count = 0

        async def side_effect(paths):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Legacy path already registered")

        mock_hass.http.async_register_static_paths = AsyncMock(side_effect=side_effect)
        registration = JSModuleRegistration(mock_hass)

        await registration._async_register_path()

        assert call_count == 2


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
        mock_lovelace.resources.async_delete_item = AsyncMock()

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

        assert mock_hass_storage_mode.http.async_register_static_paths.call_count == 2
        mock_hass_storage_mode.data["lovelace"].resources.async_create_item.assert_called()

    @pytest.mark.asyncio
    async def test_register_in_yaml_mode(self, mock_hass_yaml_mode):
        """Test async_register in YAML mode only registers static path."""
        registration = JSModuleRegistration(mock_hass_yaml_mode)

        await registration.async_register()

        assert mock_hass_yaml_mode.http.async_register_static_paths.call_count == 2
        assert (
            not hasattr(mock_hass_yaml_mode.data["lovelace"].resources, "async_create_item")
            or not mock_hass_yaml_mode.data["lovelace"].resources.async_create_item.called
        )

    @pytest.mark.asyncio
    async def test_register_without_lovelace(self):
        """Test async_register when lovelace is not available."""
        mock_hass = MagicMock()
        mock_hass.data = {}
        mock_hass.http.async_register_static_paths = AsyncMock()

        registration = JSModuleRegistration(mock_hass)

        await registration.async_register()

        assert mock_hass.http.async_register_static_paths.call_count == 2


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
        mock_lovelace.resources.async_delete_item = AsyncMock()

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}
        mock_hass.http.async_register_static_paths = AsyncMock()
        return mock_hass

    @pytest.mark.asyncio
    async def test_register_new_module(self, mock_hass_with_lovelace):
        """Test registering a new module."""
        registration = JSModuleRegistration(mock_hass_with_lovelace)

        await registration._async_register_modules()

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
        mock_hass_with_lovelace.data["lovelace"].resources.async_items = MagicMock(return_value=[existing_resource])

        registration = JSModuleRegistration(mock_hass_with_lovelace)

        await registration._async_register_modules()

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
        mock_hass_with_lovelace.data["lovelace"].resources.async_items = MagicMock(return_value=[existing_resource])

        registration = JSModuleRegistration(mock_hass_with_lovelace)

        await registration._async_register_modules()

        mock_hass_with_lovelace.data["lovelace"].resources.async_update_item.assert_not_called()
        mock_hass_with_lovelace.data["lovelace"].resources.async_create_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_modules_cleans_up_legacy_after_registration(self, mock_hass_with_lovelace):
        """Test that legacy cleanup runs AFTER new resource registration."""
        call_order = []

        async def track_create(*args, **kwargs):
            call_order.append("create")

        async def track_delete(*args, **kwargs):
            call_order.append("delete")

        legacy_resource = {"id": "legacy-1", "url": "/home_performance/home-performance-card.js"}
        mock_hass_with_lovelace.data["lovelace"].resources.async_items = MagicMock(return_value=[legacy_resource])
        mock_hass_with_lovelace.data["lovelace"].resources.async_create_item = AsyncMock(side_effect=track_create)
        mock_hass_with_lovelace.data["lovelace"].resources.async_delete_item = AsyncMock(side_effect=track_delete)

        registration = JSModuleRegistration(mock_hass_with_lovelace)
        await registration._async_register_modules()

        assert call_order == ["create", "delete"]

    @pytest.mark.asyncio
    async def test_register_modules_continues_on_create_error(self, mock_hass_with_lovelace):
        """Test that an error creating a resource is caught and logged."""
        mock_hass_with_lovelace.data["lovelace"].resources.async_create_item = AsyncMock(
            side_effect=Exception("Storage error")
        )

        registration = JSModuleRegistration(mock_hass_with_lovelace)

        await registration._async_register_modules()


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

        assert (
            not hasattr(mock_lovelace.resources, "async_delete_item")
            or not mock_lovelace.resources.async_delete_item.called
        )

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

        mock_lovelace.resources.async_delete_item.assert_not_called()


class TestJSModuleRegistrationLegacyCleanup:
    """Test JSModuleRegistration._async_cleanup_legacy_resources method."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_legacy_underscore_url(self):
        """Test that legacy resources with underscore URL are removed."""
        legacy_resource = {
            "id": "legacy-1",
            "url": "/home_performance/home-performance-card.js",
        }
        mock_lovelace = MagicMock()
        mock_lovelace.mode = "storage"
        mock_lovelace.resources.loaded = True
        mock_lovelace.resources.async_items = MagicMock(return_value=[legacy_resource])
        mock_lovelace.resources.async_delete_item = AsyncMock()

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}

        registration = JSModuleRegistration(mock_hass)

        await registration._async_cleanup_legacy_resources()

        mock_lovelace.resources.async_delete_item.assert_called_once_with("legacy-1")

    @pytest.mark.asyncio
    async def test_cleanup_ignores_new_url(self):
        """Test that new resources with hyphen URL are not removed."""
        new_resource = {
            "id": "new-1",
            "url": f"{URL_BASE}/home-performance-card.js?v=1.0",
        }
        mock_lovelace = MagicMock()
        mock_lovelace.mode = "storage"
        mock_lovelace.resources.loaded = True
        mock_lovelace.resources.async_items = MagicMock(return_value=[new_resource])
        mock_lovelace.resources.async_delete_item = AsyncMock()

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}

        registration = JSModuleRegistration(mock_hass)

        await registration._async_cleanup_legacy_resources()

        mock_lovelace.resources.async_delete_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_handles_mixed_resources(self):
        """Test cleanup with both legacy and new resources."""
        resources = [
            {"id": "legacy-1", "url": "/home_performance/home-performance-card.js"},
            {"id": "new-1", "url": f"{URL_BASE}/home-performance-card.js?v=1.0"},
            {"id": "other-1", "url": "/other-integration/card.js"},
        ]
        mock_lovelace = MagicMock()
        mock_lovelace.mode = "storage"
        mock_lovelace.resources.loaded = True
        mock_lovelace.resources.async_items = MagicMock(return_value=resources)
        mock_lovelace.resources.async_delete_item = AsyncMock()

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}

        registration = JSModuleRegistration(mock_hass)

        await registration._async_cleanup_legacy_resources()

        mock_lovelace.resources.async_delete_item.assert_called_once_with("legacy-1")

    @pytest.mark.asyncio
    async def test_cleanup_continues_on_delete_error(self):
        """Test that an error deleting one legacy resource doesn't prevent others."""
        resources = [
            {"id": "legacy-1", "url": "/home_performance/card-a.js"},
            {"id": "legacy-2", "url": "/home_performance/card-b.js"},
        ]
        mock_lovelace = MagicMock()
        mock_lovelace.mode = "storage"
        mock_lovelace.resources.loaded = True
        mock_lovelace.resources.async_items = MagicMock(return_value=resources)
        mock_lovelace.resources.async_delete_item = AsyncMock(side_effect=[Exception("Delete failed"), None])

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}

        registration = JSModuleRegistration(mock_hass)

        await registration._async_cleanup_legacy_resources()

        assert mock_lovelace.resources.async_delete_item.call_count == 2


class TestJSModuleRegistrationWaitRetries:
    """Test _async_wait_for_lovelace_resources retry behavior."""

    @pytest.mark.asyncio
    async def test_wait_gives_up_after_max_retries(self):
        """Test that waiting gives up after MAX_WAIT_RETRIES attempts."""
        mock_lovelace = MagicMock()
        mock_lovelace.mode = "storage"
        mock_lovelace.resources.loaded = False

        mock_hass = MagicMock()
        mock_hass.data = {"lovelace": mock_lovelace}

        scheduled_callbacks = []

        def fake_call_later(hass, delay, callback):
            scheduled_callbacks.append(callback)

        registration = JSModuleRegistration(mock_hass)

        with patch(
            "custom_components.home_performance.frontend.async_call_later",
            side_effect=fake_call_later,
        ):
            await registration._async_wait_for_lovelace_resources()

            for _ in range(20):
                if not scheduled_callbacks:
                    break
                cb = scheduled_callbacks.pop(0)
                await cb(None)

        from custom_components.home_performance.frontend import _MAX_WAIT_RETRIES

        assert len(scheduled_callbacks) == 0
        assert _ <= _MAX_WAIT_RETRIES
