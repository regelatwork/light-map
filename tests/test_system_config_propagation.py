from multiprocessing import Event, Queue
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

from light_map.core.common_types import AppConfig, ProjectorPose
from light_map.map.map_config import MapConfigManager
from light_map.persistence.persistence_service import PersistenceService
from light_map.rendering.layers.door_layer import DoorLayer
from light_map.rendering.layers.hand_mask_layer import HandMaskLayer
from light_map.rendering.projection import Projector3DModel
from light_map.state.world_state import WorldState
from light_map.vision.remote.remote_driver import create_app


@pytest.fixture
def mock_app_and_service(tmp_path):
    config_file = str(tmp_path / "map_config.json")
    map_config = MapConfigManager(config_file)

    app = MagicMock()
    app.map_config = map_config
    app.state = WorldState()
    app.config = MagicMock(spec=AppConfig)
    app.config.projector_ppi = 96.0
    app.config.use_projector_3d_model = True
    app.config.projector_pos_x_override = None
    app.config.projector_pos_y_override = None
    app.config.projector_pos_z_override = None

    proj_model = MagicMock(spec=Projector3DModel)
    proj_model.calibrated_projector_center = np.array([10.0, 20.0, 300.0], dtype=np.float32)
    proj_model.use_3d = True
    app.config.projector_3d_model = proj_model

    service = PersistenceService(app)
    service.sync_projector_pose()
    return app, service


def test_update_system_config_projector_position_updates_pose_and_version(mock_app_and_service):
    app, service = mock_app_and_service
    initial_pose = app.state.projector_pose
    initial_version = app.state.projector_pose_version

    assert initial_pose.x == 10.0
    assert initial_pose.y == 20.0
    assert initial_pose.z == 300.0

    success = service.update_system_config(
        {
            "action": "UPDATE_SYSTEM_CONFIG",
            "projector_pos_x_override": 150.0,
        }
    )
    assert success is True

    new_pose = app.state.projector_pose
    assert new_pose.x == 150.0
    assert new_pose.y == 20.0
    assert new_pose.z == 300.0
    assert app.state.projector_pose_version > initial_version


def test_update_system_config_projector_position_reset_to_calibrated(mock_app_and_service):
    app, service = mock_app_and_service

    service.update_system_config(
        {
            "projector_pos_x_override": 150.0,
        }
    )
    assert app.state.projector_pose.x == 150.0
    version_after_override = app.state.projector_pose_version

    # Reset by passing None (as from null in JSON)
    success = service.update_system_config(
        {
            "projector_pos_x_override": None,
        }
    )
    assert success is True

    reset_pose = app.state.projector_pose
    assert reset_pose.x == 10.0
    assert app.state.projector_pose_version > version_after_override


def test_update_system_config_use_projector_3d_model_sync(mock_app_and_service):
    app, service = mock_app_and_service
    app.config.projector_3d_model.use_3d = True

    service.update_system_config({"use_projector_3d_model": False})
    assert app.config.use_projector_3d_model is False
    assert app.config.projector_3d_model.use_3d is False

    service.update_system_config({"use_projector_3d_model": True})
    assert app.config.use_projector_3d_model is True
    assert app.config.projector_3d_model.use_3d is True


def test_hand_mask_layer_version_tracks_config_and_projector_pose():
    ws = WorldState()
    config = MagicMock(spec=AppConfig)
    config.enable_hand_masking = True

    layer = HandMaskLayer(ws, config)
    v1 = layer.get_current_version()

    # Updating projector pose should bump HandMaskLayer version
    ws.projector_pose = ProjectorPose(10.0, 20.0, 30.0)
    v2 = layer.get_current_version()
    assert v2 > v1

    # Updating config should also refresh HandMaskLayer version
    ws.invalidate_config()
    v3 = layer.get_current_version()
    assert v3 > v2


def test_door_layer_version_tracks_config_version():
    ws = WorldState()
    config = MagicMock(spec=AppConfig)
    config.door_thickness_multiplier = 3.0

    layer = DoorLayer(ws, 1920, 1080, config=config)
    v1 = layer.get_current_version()

    ws.invalidate_config()
    v2 = layer.get_current_version()
    assert v2 > v1


def test_remote_driver_config_system_preserves_null_for_reset():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    fastapi_app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(fastapi_app)

    response = client.post("/config/system", json={"projector_pos_x_override": None})
    assert response.status_code == 200

    result = results_queue.get(timeout=1.0)
    assert result.data["action"] == "UPDATE_SYSTEM_CONFIG"
    assert "projector_pos_x_override" in result.data
    assert result.data["projector_pos_x_override"] is None


def test_remote_driver_config_system_accepts_all_global_settings():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    fastapi_app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(fastapi_app)

    payload = {
        "door_thickness_multiplier": 5.0,
        "use_projector_3d_model": False,
        "projector_ppi": 120.0,
        "projector_pos_y_override": 75.5,
    }
    response = client.post("/config/system", json=payload)
    assert response.status_code == 200

    result = results_queue.get(timeout=1.0)
    assert result.data["action"] == "UPDATE_SYSTEM_CONFIG"
    assert result.data["door_thickness_multiplier"] == 5.0
    assert result.data["use_projector_3d_model"] is False
    assert result.data["projector_ppi"] == 120.0
    assert result.data["projector_pos_y_override"] == 75.5
