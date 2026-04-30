from unittest.mock import MagicMock

import numpy as np
import pytest

from light_map.core.app_context import MainContext
from light_map.core.common_types import AppConfig, SceneId
from light_map.core.scene_manager import SceneManager
from light_map.interactive_app import InteractiveApp
from light_map.persistence.persistence_service import PersistenceService
from light_map.vision.environment_manager import EnvironmentManager


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.width = 100
    config.height = 100
    config.map_search_patterns = []
    config.storage_manager = None
    config.projector_matrix = np.eye(3)
    config.distortion_model = None
    config.enable_hand_masking = False
    config.hand_mask_padding = 0
    config.camera_resolution = (100, 100)
    config.projector_matrix_resolution = (100, 100)
    config.projector_ppi = 96.0
    # Add other required attributes
    config.camera_matrix = np.eye(3)
    config.distortion_coefficients = np.zeros(5)
    config.rotation_vector = np.zeros(3)
    config.translation_vector = np.zeros(3)
    config.projector_3d_model = MagicMock()
    config.projector_3d_model.calibrated_projector_center = [0, 0, 1000]
    return config


def test_interactive_app_initialization(mock_config, monkeypatch):
    # Mock _load_camera_calibration to avoid file system calls
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    # Mock Projector3DModel.load_from_storage
    from light_map.rendering.projection import Projector3DModel

    monkeypatch.setattr(
        Projector3DModel,
        "load_from_storage",
        lambda *args, **kwargs: mock_config.projector_3d_model,
    )

    app = InteractiveApp(mock_config)

    # Verify tiered context
    assert isinstance(app.app_context, MainContext)

    # Verify managers are initialized
    assert isinstance(app.persistence_service, PersistenceService)
    assert isinstance(app.environment_manager, EnvironmentManager)
    assert isinstance(app.scene_manager, SceneManager)

    # Verify context distribution
    assert app.persistence_service.app == app
    assert app.environment_manager.context == app.app_context
    assert app.scene_manager.context == app.app_context


def test_interactive_app_delegation(mock_config, monkeypatch):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )
    from light_map.rendering.projection import Projector3DModel

    monkeypatch.setattr(
        Projector3DModel,
        "load_from_storage",
        lambda *args, **kwargs: mock_config.projector_3d_model,
    )

    app = InteractiveApp(mock_config)

    # Mock managers
    app.persistence_service = MagicMock(spec=PersistenceService)
    app.environment_manager = MagicMock(spec=EnvironmentManager)
    app.scene_manager = MagicMock(spec=SceneManager)

    # Test delegation: load_map
    app.load_map("test_map.svg")
    app.persistence_service.load_map.assert_called_once_with("test_map.svg", False)

    # Test delegation: save_session
    app.save_session()
    app.persistence_service.save_session.assert_called_once()

    # Test delegation: sync_vision
    app._sync_vision(app.state)
    app.environment_manager.sync_vision.assert_called_once_with(app.state)

    # Test delegation: scene transition
    from light_map.core.scene import SceneTransition

    transition = SceneTransition(target_scene=SceneId.VIEWING)
    app._switch_scene(transition)
    app.scene_manager.handle_transition.assert_called_once_with(transition)


def test_interactive_app_process_state_delegation(mock_config, monkeypatch):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )
    from light_map.rendering.projection import Projector3DModel

    monkeypatch.setattr(
        Projector3DModel,
        "load_from_storage",
        lambda *args, **kwargs: mock_config.projector_3d_model,
    )

    app = InteractiveApp(mock_config)

    # Mock scene manager and current scene
    app.scene_manager = MagicMock(spec=SceneManager)
    app.scene_manager.current_scene_id = SceneId.MAP
    mock_scene = MagicMock()
    mock_scene.update.return_value = None
    mock_scene.__class__.__name__ = "MockScene"
    app.scene_manager.current_scene = mock_scene
    app.scene_manager.get_layer_stack.return_value = []

    # Mock renderer
    app.renderer = MagicMock()
    app.renderer.render.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

    # Run process_state
    app.process_state()

    # Verify delegation to scene_manager
    app.scene_manager.get_layer_stack.assert_called_once()
    mock_scene.update.assert_called_once()
    app.renderer.render.assert_called_once()
