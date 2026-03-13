import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp
from light_map.common_types import AppConfig, SessionData, ViewportState
from light_map.visibility_types import VisibilityBlocker, VisibilityType


@pytest.fixture
def mock_config(tmp_path):
    config = MagicMock(spec=AppConfig)
    config.width = 100
    config.height = 100
    config.map_search_patterns = []

    # Setup a temporary data directory
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    storage = MagicMock()
    storage.get_data_dir.return_value = str(data_dir)
    storage.get_config_path.side_effect = lambda f: str(data_dir / f)
    storage.get_state_path.side_effect = lambda f: str(data_dir / f)
    storage.get_data_path.side_effect = lambda f: str(data_dir / f)

    config.storage_manager = storage
    config.projector_matrix = np.eye(3)
    config.distortion_model = None
    config.enable_hand_masking = False
    config.hand_mask_padding = 0
    config.camera_resolution = (100, 100)
    config.projector_matrix_resolution = (100, 100)
    config.projector_ppi = 96.0
    config.door_thickness_multiplier = 3.0
    return config


def test_door_state_restoration_syncs_to_state(mock_config, monkeypatch, tmp_path):
    # 1. Setup Mock Map and Session
    map_file = str(tmp_path / "test_map.svg")
    with open(map_file, "w") as f:
        f.write('<svg width="100" height="100"></svg>')

    # Mock SVGLoader to return a door
    mock_loader = MagicMock()
    door = VisibilityBlocker(
        segments=[(0, 0), (10, 10)],
        type=VisibilityType.DOOR,
        layer_name="doors",
        id="door1",
        is_open=False,
    )
    mock_loader.get_visibility_blockers.return_value = [door]
    mock_loader.svg.width = 100
    mock_loader.svg.height = 100
    mock_loader.detect_grid_spacing.return_value = (50.0, 0.0, 0.0)

    monkeypatch.setattr("light_map.interactive_app.SVGLoader", lambda f: mock_loader)
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    # 2. Setup Session with open door
    session_data = SessionData(
        map_file=map_file,
        viewport=ViewportState(),
        tokens=[],
        door_states={"door1": True},
    )

    with patch(
        "light_map.session_manager.SessionManager.load_for_map",
        return_value=session_data,
    ):
        app = InteractiveApp(mock_config)
        app.load_map(map_file, load_session=True)

        # 3. Verify door is open in engine
        engine_door = next(b for b in app.visibility_engine.blockers if b.id == "door1")
        assert engine_door.is_open is True

        # 4. Verify door is open in state (The fix we implemented)
        state_door = next(b for b in app.state.blockers if b["id"] == "door1")
        assert state_door["is_open"] is True

        # 5. Verify visibility_timestamp was incremented
        assert app.state.visibility_timestamp > 0


def test_toggle_door_syncs_to_state(mock_config, monkeypatch, tmp_path):
    # Similar setup but for TOGGLE_DOOR action
    map_file = str(tmp_path / "test_map.svg")
    with open(map_file, "w") as f:
        f.write('<svg width="100" height="100"></svg>')

    mock_loader = MagicMock()
    door = VisibilityBlocker(
        segments=[(0, 0), (10, 10)],
        type=VisibilityType.DOOR,
        layer_name="doors",
        id="door1",
        is_open=False,
    )
    mock_loader.get_visibility_blockers.return_value = [door]
    mock_loader.svg.width = 100
    mock_loader.svg.height = 100
    mock_loader.detect_grid_spacing.return_value = (50.0, 0.0, 0.0)

    monkeypatch.setattr("light_map.interactive_app.SVGLoader", lambda f: mock_loader)
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)
    app.load_map(map_file)

    # Ensure door is closed initially
    assert app.state.blockers[0]["is_open"] is False
    initial_timestamp = app.state.visibility_timestamp

    # Inject TOGGLE_DOOR action
    app._handle_payloads({"action": "TOGGLE_DOOR", "payload": "door1"}, app.state)

    # Verify door is now open in state
    assert app.state.blockers[0]["is_open"] is True
    assert app.state.visibility_timestamp > initial_timestamp
