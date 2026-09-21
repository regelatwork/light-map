from unittest.mock import MagicMock

import numpy as np
import pytest

from light_map.core.app_context import AppContext
from light_map.core.common_types import AppConfig, Token
from light_map.rendering.layers.overlay_layer import DebugLayer
from light_map.rendering.overlay_renderer import OverlayRenderer
from light_map.state.world_state import WorldState
from light_map.vision.detectors.aruco_detector import ArucoTokenDetector


@pytest.fixture
def mock_app_context():
    config = MagicMock(spec=AppConfig)
    config.width = 1920
    config.height = 1080

    ctx = MagicMock(spec=AppContext)
    ctx.app_config = config
    ctx.debug_mode = True
    ctx.show_tokens = True

    ctx.map_config_manager = MagicMock()
    ctx.map_config_manager.get_ppi.return_value = 50.0

    mock_map_system = MagicMock()
    mock_map_system.world_to_screen.side_effect = lambda wx, wy: (float(wx * 2), float(wy * 2))
    ctx.map_system = mock_map_system

    ctx.notifications = MagicMock()
    ctx.notifications.get_active_notifications.return_value = []

    return ctx


def test_token_is_stereo_default():
    t = Token(id=1, world_x=10.0, world_y=20.0)
    assert t.is_stereo is False
    assert t.marker_z == 0.0

    d = t.to_dict()
    assert "is_stereo" in d
    assert d["is_stereo"] is False

    t_stereo = Token(id=2, world_x=10.0, world_y=20.0, marker_z=48.5, is_stereo=True)
    assert t_stereo.is_stereo is True
    assert t_stereo.marker_z == 48.5
    assert t_stereo.to_dict()["is_stereo"] is True


def test_aruco_detector_map_to_tokens_stereo():
    detector = ArucoTokenDetector()
    map_system = MagicMock()
    map_system.world_mm_to_svg.side_effect = lambda x, y, ppi: (x, y)

    corners_l = np.array([[100, 100], [150, 100], [150, 150], [100, 150]], dtype=np.float32)
    corners_r = np.array([[90, 100], [140, 100], [140, 150], [90, 150]], dtype=np.float32)

    raw_data = {
        "ids": [42],
        "corners": [corners_l],
        "corners_right_dict": {42: corners_r},
    }

    mock_triangulator = MagicMock()
    # Triangulate to 3D with Z=45.5mm
    mock_triangulator.triangulate_corners.return_value = np.array(
        [
            [10.0, 20.0, 45.0],
            [20.0, 20.0, 45.0],
            [20.0, 30.0, 46.0],
            [10.0, 30.0, 46.0],
        ],
        dtype=np.float32,
    )

    tokens = detector.map_to_tokens(
        raw_data,
        map_system,
        stereo_triangulator=mock_triangulator,
    )

    assert len(tokens) == 1
    t = tokens[0]
    assert t.id == 42
    assert t.is_stereo is True
    assert t.marker_z == pytest.approx(45.5, rel=1e-2)
    mock_triangulator.triangulate_corners.assert_called_once()


def test_aruco_detector_map_to_tokens_fallback():
    detector = ArucoTokenDetector()
    map_system = MagicMock()
    map_system.world_mm_to_svg.side_effect = lambda x, y, ppi: (x, y)

    corners_l = np.array([[100, 100], [150, 100], [150, 150], [100, 150]], dtype=np.float32)

    # Right camera did not see marker 42
    raw_data = {
        "ids": [42],
        "corners": [corners_l],
        "corners_right_dict": {},
    }

    mock_triangulator = MagicMock()
    mock_triangulator.intersect_corners_ray_plane.return_value = np.array(
        [
            [10.0, 20.0, 50.0],
            [20.0, 20.0, 50.0],
            [20.0, 30.0, 50.0],
            [10.0, 30.0, 50.0],
        ],
        dtype=np.float32,
    )

    tokens = detector.map_to_tokens(
        raw_data,
        map_system,
        default_height_mm=50.0,
        stereo_triangulator=mock_triangulator,
    )

    assert len(tokens) == 1
    t = tokens[0]
    assert t.id == 42
    assert t.is_stereo is False
    assert t.marker_z == 50.0


def test_debug_layer_token_versioning(mock_app_context):
    ws = WorldState()
    layer = DebugLayer(ws, mock_app_context)

    v1 = layer.get_current_version()

    # Update tokens
    ws.tokens = [Token(id=1, world_x=50.0, world_y=50.0, is_stereo=True, marker_z=47.2)]
    v2 = layer.get_current_version()

    assert v2 > v1


def test_overlay_renderer_draw_debug_overlay_tokens(mock_app_context):
    renderer = OverlayRenderer(mock_app_context)

    tokens = [
        Token(id=1, world_x=100.0, world_y=100.0, is_stereo=True, marker_z=48.2),
        Token(id=2, world_x=200.0, world_y=200.0, is_stereo=False, marker_z=50.0),
    ]

    patches = renderer.draw_debug_overlay(
        fps=60.0,
        current_scene_name="TestScene",
        inputs=[],
        tokens=tokens,
    )

    # Should have top-left banner patch + 1 patch for each token
    assert len(patches) >= 3

    # Verify patches have valid dimensions and non-empty pixel data
    for p in patches:
        assert p.width > 0
        assert p.height > 0
        assert p.data.shape == (p.height, p.width, 4)


def test_debug_layer_renders_tokens_when_debug_mode_on(mock_app_context):
    ws = WorldState()
    ws.tokens = [
        Token(id=1, world_x=100.0, world_y=100.0, is_stereo=True, marker_z=48.2),
    ]

    mock_app_context.debug_mode = True
    layer = DebugLayer(ws, mock_app_context)

    patches, _ = layer.render()
    assert len(patches) >= 2  # top-left banner + token debug patch

    # Toggle debug mode off
    mock_app_context.debug_mode = False
    patches_off, _ = layer.render()
    assert len(patches_off) == 0


def test_aruco_worker_stereo_detection():
    import multiprocessing as mp

    import cv2

    from light_map.vision.infrastructure.camera_operator import CameraOperator
    from light_map.vision.infrastructure.workers import aruco_worker

    w, h = 320, 240
    op_l = CameraOperator(width=w, height=h, num_consumers=1)
    op_r = CameraOperator(width=w, height=h, num_consumers=1)

    lock_l = mp.Lock()
    lock_r = mp.Lock()
    op_l.lock = lock_l
    op_r.lock = lock_r

    # Create synthetic image with ArUco marker 5
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, 5, 80)
    marker_bgr = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

    frame_l = np.full((h, w, 3), 255, dtype=np.uint8)
    frame_l[50:130, 50:130] = marker_bgr

    frame_r = np.full((h, w, 3), 255, dtype=np.uint8)
    frame_r[50:130, 40:120] = marker_bgr

    op_l._publish_frame(frame_l, timestamp=1000)
    op_r._publish_frame(frame_r, timestamp=1000)

    results_queue = mp.Queue()
    stop_event = mp.Event()

    p = mp.Process(
        target=aruco_worker,
        args=(op_l.shm_name, results_queue, lock_l, stop_event),
        kwargs={
            "width": w,
            "height": h,
            "num_consumers": 1,
            "shm_name_right": op_r.shm_name,
            "lock_right": lock_r,
            "width_right": w,
            "height_right": h,
        },
    )
    try:
        p.start()
        result = results_queue.get(timeout=3.0)
        assert result is not None
        assert 5 in result.data["ids"]
        assert "corners_right_dict" in result.data
        assert 5 in result.data["corners_right_dict"]
    finally:
        stop_event.set()
        p.join(timeout=1.0)
        if p.is_alive():
            p.kill()
        op_l.cleanup()
        op_r.cleanup()
