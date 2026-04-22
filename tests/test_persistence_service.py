import pytest
import os
from unittest.mock import MagicMock, patch
from light_map.persistence.persistence_service import PersistenceService
from light_map.state.world_state import WorldState
from light_map.core.common_types import MapRenderState, GridType


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.state = WorldState()
    app.map_config = MagicMock()
    app.map_system = MagicMock()
    app.layer_manager = MagicMock()
    app.layer_manager.map_layer.opacity = 1.0
    app.layer_manager.map_layer.quality = 1.0
    app.fow_manager = None
    app.current_map_path = None
    return app


def test_load_map_updates_state(mock_app):
    service = PersistenceService(mock_app)
    filename = "/fake/path/map.svg"

    # Mock MapEntry and MapConfig data structure
    mock_entry = MagicMock()
    mock_entry.grid_spacing_svg = 10.0
    mock_entry.fow_disabled = True
    mock_app.map_config.data.maps = {os.path.abspath(filename): mock_entry}

    with patch(
        "light_map.persistence.persistence_service.SVGLoader"
    ) as mock_svg_loader:
        mock_svg_loader.return_value.filename = os.path.abspath(filename)
        service.load_map(filename)

    assert mock_app.current_map_path == os.path.abspath(filename)
    assert isinstance(mock_app.state.map_render_state, MapRenderState)
    assert mock_app.state.map_render_state.filepath == os.path.abspath(filename)
    assert mock_app.state.fow_disabled is True

    # Verify app methods called
    mock_app._rebuild_visibility_stack.assert_called_once_with(mock_entry)
    mock_app.refresh_base_scale.assert_called_once()
    mock_app.switch_to_viewing.assert_called_once()


def test_update_token_persists_and_updates_version(mock_app):
    service = PersistenceService(mock_app)
    initial_version = mock_app.state.config_data

    token_id = 42
    kwargs = {"name": "New Name", "color": "#FF0000", "is_map_override": False}

    # Mock existing global default
    mock_app.map_config.data.global_settings.aruco_defaults = {}
    mock_app.map_config.data.maps = {}

    service.update_token(token_id, **kwargs)

    mock_app.map_config.set_global_aruco_definition.assert_called_once_with(
        aruco_id=token_id,
        name="New Name",
        type="NPC",
        profile=None,
        size=None,
        height_mm=None,
        color="#FF0000",
    )

    assert mock_app.state.config_data == initial_version + 1


def test_update_grid_updates_version(mock_app):
    service = PersistenceService(mock_app)
    initial_version = mock_app.state.config_data

    map_path = "/fake/path/map.svg"
    mock_app.current_map_path = os.path.abspath(map_path)
    mock_entry = MagicMock()
    mock_app.map_config.data.maps = {os.path.abspath(map_path): mock_entry}

    service.update_grid(map_path, spacing=50.0, offset_x=10.0)

    assert mock_entry.grid_spacing_svg == 50.0
    assert mock_entry.grid_origin_svg_x == 10.0
    assert mock_app.state.grid_spacing_svg == 50.0
    assert mock_app.state.grid_origin_svg_x == 10.0

    mock_app.map_config.save.assert_called_once()
    mock_app.refresh_base_scale.assert_called_once()
    assert mock_app.state.config_data == initial_version + 1


def test_update_grid_invalid_type(mock_app):
    service = PersistenceService(mock_app)
    map_path = "/fake/path/map.svg"
    mock_app.current_map_path = os.path.abspath(map_path)
    mock_entry = MagicMock()
    mock_entry.grid_type = GridType.SQUARE
    mock_app.map_config.data.maps = {os.path.abspath(map_path): mock_entry}

    service.update_grid(map_path, grid_type="INVALID")

    # Should stay SQUARE
    assert mock_entry.grid_type == GridType.SQUARE
