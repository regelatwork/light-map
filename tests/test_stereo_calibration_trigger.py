import json
from unittest.mock import MagicMock, patch

import numpy as np

from light_map.action_dispatcher import ActionDispatcher
from light_map.core.common_types import AppConfig, MenuActions, SceneId
from light_map.core.scene import SceneTransition
from light_map.core.scene_manager import SceneManager
from light_map.map.map_config import MapConfigManager
from light_map.menu.menu_builder import build_root_menu
from light_map.menu.menu_scene import MenuScene
from light_map.menu.menu_system import MenuState
from light_map.persistence.persistence_service import PersistenceService


def test_stereo_enums_exist():
    """Verify that CALIBRATE_STEREO is defined in MenuActions and SceneId."""
    assert hasattr(MenuActions, "CALIBRATE_STEREO")
    assert MenuActions.CALIBRATE_STEREO == "CALIBRATE_STEREO"
    assert hasattr(SceneId, "CALIBRATE_STEREO")
    assert SceneId.CALIBRATE_STEREO == "CALIBRATE_STEREO"


def test_menu_builder_contains_stereo_calibration():
    """Verify that the Calibration menu contains the Stereo Vision Calibration item."""
    map_config = MagicMock(spec=MapConfigManager)
    map_config.data = MagicMock()
    map_config.data.maps = {}
    menu = build_root_menu(map_config)

    # Find the Calibration sub-menu
    calib_item = next((item for item in menu.children if item.title == "Calibration"), None)
    assert calib_item is not None, "Calibration menu item not found"

    stereo_item = next(
        (
            child
            for child in calib_item.children
            if getattr(child, "action_id", None) == MenuActions.CALIBRATE_STEREO
        ),
        None,
    )
    assert stereo_item is not None, "Stereo calibration item not found in Calibration menu"
    assert "Stereo" in stereo_item.title


def test_menu_scene_handles_calibrate_stereo():
    """Verify MenuScene transitions to CALIBRATE_STEREO when triggered."""
    mock_context = MagicMock()
    scene = MenuScene(mock_context)

    mock_menu_state = MenuState(
        current_menu_title="",
        active_items=[],
        item_rects=[],
        hovered_item_index=None,
        feedback_item_index=None,
        prime_progress=0.0,
        summon_progress=0.0,
        cursor_pos=None,
        is_visible=True,
        just_triggered_action=MenuActions.CALIBRATE_STEREO,
    )
    with patch.object(scene.menu_system, "update", return_value=mock_menu_state):
        transition = scene.update(inputs=[], actions=[], current_time=0.0)

    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.CALIBRATE_STEREO


def test_action_dispatcher_calibrate_stereo_enabled():
    """Verify ActionDispatcher transitions to CALIBRATE_STEREO when stereo is enabled."""
    mock_app = MagicMock()
    mock_app.app_config.stereo_vision.enable_stereo = True
    dispatcher = ActionDispatcher(mock_app)

    transition = dispatcher.dispatch({"action": MenuActions.CALIBRATE_STEREO})
    assert transition is not None
    assert transition.target_scene == SceneId.CALIBRATE_STEREO


def test_action_dispatcher_calibrate_stereo_disabled():
    """Verify ActionDispatcher aborts and notifies if stereo is disabled."""
    mock_app = MagicMock()
    mock_app.app_config.stereo_vision.enable_stereo = False
    dispatcher = ActionDispatcher(mock_app)

    transition = dispatcher.dispatch({"action": MenuActions.CALIBRATE_STEREO})
    assert transition is None
    mock_app.notifications.add_notification.assert_called_once()
    assert "Stereo vision" in mock_app.notifications.add_notification.call_args[0][0]


def test_persistence_service_save_stereo_calibration(tmp_path):
    """Verify PersistenceService saves stereo calibration data properly."""
    mock_app = MagicMock()
    mock_app.config.storage_manager.get_data_path.side_effect = lambda f: str(tmp_path / f)
    service = PersistenceService(mock_app)

    dummy_data = {
        "roi_left": [0, 0, 100, 100],
        "roi_right": [10, 10, 110, 110],
        "r_stereo": np.eye(3),
        "t_stereo": np.array([128.0, 0.0, 0.0]),
    }
    output_file = service.save_stereo_calibration(dummy_data)
    assert (tmp_path / "stereo_calibration.json").exists()

    with open(output_file) as f:
        saved = json.load(f)
    assert saved["roi_left"] == [0, 0, 100, 100]
    assert saved["t_stereo"] == [128.0, 0.0, 0.0]


def test_scene_manager_reflects_scene_name():
    """Verify SceneManager records class name in state._scene_atom."""
    mock_context = MagicMock()
    mock_context.app_config = AppConfig(width=1920, height=1080, projector_matrix=np.eye(3))
    mock_state = MagicMock()
    mock_state._scene_atom = MagicMock()

    manager = SceneManager(mock_context, mock_state)
    manager.transition_to(SceneId.CALIBRATE_STEREO)
    assert manager.current_scene_id == SceneId.CALIBRATE_STEREO
    mock_state._scene_atom.update.assert_called_with("StereoCalibrationScene")


def test_toggle_stereo_enums_exist():
    """Verify that TOGGLE_STEREO_VISION is defined in MenuActions."""
    assert hasattr(MenuActions, "TOGGLE_STEREO_VISION")
    assert MenuActions.TOGGLE_STEREO_VISION == "TOGGLE_STEREO_VISION"


def test_menu_builder_contains_toggle_stereo():
    """Verify that the Options menu contains the Toggle Stereo Vision item."""
    map_config = MagicMock(spec=MapConfigManager)
    map_config.data = MagicMock()
    map_config.data.maps = {}
    map_config.data.global_settings.stereo_vision.enable_stereo = False
    menu = build_root_menu(map_config)

    options_item = next((item for item in menu.children if item.title == "Options"), None)
    assert options_item is not None, "Options menu item not found"

    stereo_toggle = next(
        (
            child
            for child in options_item.children
            if getattr(child, "action_id", None) == MenuActions.TOGGLE_STEREO_VISION
        ),
        None,
    )
    assert stereo_toggle is not None
    assert "Stereo Vision: OFF" in stereo_toggle.title


def test_persistence_service_toggle_stereo_vision():
    """Verify PersistenceService toggles stereo vision mode and persists."""
    mock_app = MagicMock()
    mock_app.config.stereo_vision.enable_stereo = False
    mock_app.map_config.data.global_settings.stereo_vision.enable_stereo = False
    service = PersistenceService(mock_app)

    new_val = service.toggle_stereo_vision()
    assert new_val is True
    assert mock_app.map_config.data.global_settings.stereo_vision.enable_stereo is True
    assert mock_app.config.stereo_vision.enable_stereo is True
    mock_app.map_config.save.assert_called_once()

    new_val2 = service.toggle_stereo_vision()
    assert new_val2 is False
    assert mock_app.map_config.data.global_settings.stereo_vision.enable_stereo is False
    assert mock_app.config.stereo_vision.enable_stereo is False


def test_action_dispatcher_toggle_stereo_vision():
    """Verify ActionDispatcher handles TOGGLE_STEREO_VISION action."""
    mock_app = MagicMock()
    mock_app.persistence_service.toggle_stereo_vision.return_value = True
    dispatcher = ActionDispatcher(mock_app)

    res = dispatcher.dispatch({"action": "TOGGLE_STEREO_VISION"})
    assert res is None
    mock_app.persistence_service.toggle_stereo_vision.assert_called_once()
    mock_app.notifications.add_notification.assert_called_once_with("Stereo Vision ON")
