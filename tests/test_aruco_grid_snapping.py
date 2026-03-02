import pytest
import numpy as np
import os
from unittest.mock import MagicMock
from light_map.common_types import AppConfig, TokenDetectionAlgorithm


@pytest.fixture
def grid_svg_file(tmp_path):
    svg_content = """<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
  <!-- Grid lines at 50px intervals -->
  <line x1="0" y1="50" x2="200" y2="50" stroke="black" />
  <line x1="0" y1="100" x2="200" y2="100" stroke="black" />
  <line x1="0" y1="150" x2="200" y2="150" stroke="black" />
  
  <line x1="50" y1="0" x2="50" y2="200" stroke="black" />
  <line x1="100" y1="0" x2="100" y2="200" stroke="black" />
  <line x1="150" y1="0" x2="150" y2="200" stroke="black" />
</svg>"""
    f = tmp_path / "test_grid.svg"
    f.write_text(svg_content)
    return str(f)


def test_aruco_detection_snapped_to_detected_grid(grid_svg_file, tmp_path):
    # Setup
    from light_map.interactive_app import InteractiveApp

    config = AppConfig(
        width=1920,
        height=1080,
        projector_matrix=np.eye(3, dtype=np.float32),
        storage_manager=MagicMock(),
    )
    config.storage_manager.get_config_path.side_effect = lambda x: str(tmp_path / x)
    config.storage_manager.get_data_path.side_effect = lambda x: str(tmp_path / x)
    config.storage_manager.get_data_dir.return_value = str(tmp_path)

    # We need dummy calibration files for InteractiveApp._load_camera_calibration
    intr_path = tmp_path / "camera_calibration.npz"
    extr_path = tmp_path / "camera_extrinsics.npz"
    np.savez(intr_path, camera_matrix=np.eye(3), dist_coeffs=np.zeros(5))
    np.savez(extr_path, rvec=np.zeros(3), tvec=np.zeros(3))

    app = InteractiveApp(config)
    app.load_map(grid_svg_file)

    # Verify grid was detected
    entry = app.map_config.data.maps.get(os.path.abspath(grid_svg_file))
    assert entry.grid_spacing_svg == 50.0

    # Setup for tracking
    app.map_config.data.global_settings.detection_algorithm = (
        TokenDetectionAlgorithm.ARUCO
    )

    from light_map.common_types import Token

    fixed_token = Token(id=1, world_x=53.0, world_y=102.0, world_z=0.0)

    app.app_context.aruco_detector.detect_tokens = MagicMock(return_value=[fixed_token])

    # We need to run the tracking loop part. In InteractiveApp, it's usually handled by scenes.
    # But TrackingCoordinator is what we want to test.

    coordinator = app.tracking_coordinator
    dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    # Mock token_tracker.detect_tokens to return our fixed token
    # (TrackingCoordinator uses its own token_tracker)
    coordinator.token_tracker.detect_tokens = MagicMock(return_value=[fixed_token])

    coordinator.process_aruco_tracking(
        dummy_frame, config, app.map_system, app.map_config
    )

    # Verify results
    tokens = app.map_system.ghost_tokens
    assert len(tokens) == 1
    token = tokens[0]

    print(f"Token position: ({token.world_x}, {token.world_y})")

    # Should be snapped to (75, 125)
    assert token.world_x == 75.0
    assert token.world_y == 125.0
