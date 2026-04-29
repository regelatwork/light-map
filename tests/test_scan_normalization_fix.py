import os

import numpy as np

from light_map.core.common_types import AppConfig
from light_map.interactive_app import InteractiveApp


def test_svg_loader_path_normalization(tmp_path):
    from light_map.rendering.svg import SVGLoader

    # Create a dummy svg file
    svg_file = tmp_path / "test.svg"
    svg_file.write_text('<svg width="100" height="100"></svg>')

    # Load with relative path (mock current dir)
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        loader = SVGLoader("test.svg")
        assert os.path.isabs(loader.filename)
        assert loader.filename == os.path.abspath("test.svg")
    finally:
        os.chdir(original_cwd)


def test_interactive_app_resolution_sync(tmp_path):
    from light_map.core.storage import StorageManager

    storage = StorageManager(base_dir=str(tmp_path))
    storage.ensure_dirs()

    # Create dummy calibration files
    data_dir = storage.data_dir
    camera_matrix = np.eye(3, dtype=np.float32)
    distortion_coefficients = np.zeros(5, dtype=np.float32)
    rotation_vector = np.zeros((3, 1), dtype=np.float32)
    translation_vector = np.zeros((3, 1), dtype=np.float32)

    np.savez(
        data_dir / "camera_calibration.npz",
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion_coefficients,
    )
    np.savez(
        data_dir / "camera_extrinsics.npz",
        rotation_vector=rotation_vector,
        translation_vector=translation_vector,
    )

    transformation_matrix = np.eye(3, dtype=np.float32)
    config = AppConfig(
        width=640,
        height=480,
        projector_matrix=transformation_matrix,
        storage_manager=storage,
    )
    # Still use patch for instantiation if we want, but reload_config will call it again.
    # It's better to just have the files.
    app = InteractiveApp(config)

    assert app.map_system.width == 640
    assert app.map_system.height == 480

    new_config = AppConfig(
        width=1280,
        height=720,
        projector_matrix=transformation_matrix,
        storage_manager=storage,
    )
    app.reload_config(new_config)

    assert app.map_system.width == 1280
    assert app.map_system.height == 720


def test_token_tracker_determinism():
    from light_map.vision.processing.token_tracker import TokenTracker

    tracker = TokenTracker()

    _, points1 = tracker.get_scan_pattern(1000, 1000, 100)
    _, points2 = tracker.get_scan_pattern(1000, 1000, 100)

    assert points1 == points2


def test_interactive_app_load_map_normalization(tmp_path):
    from light_map.core.storage import StorageManager
    from light_map.map.map_config import MapEntry

    storage = StorageManager(base_dir=str(tmp_path))
    storage.ensure_dirs()

    # Create dummy calibration files
    data_dir = storage.data_dir
    camera_matrix = np.eye(3, dtype=np.float32)
    distortion_coefficients = np.zeros(5, dtype=np.float32)
    rotation_vector = np.zeros((3, 1), dtype=np.float32)
    translation_vector = np.zeros((3, 1), dtype=np.float32)

    np.savez(
        data_dir / "camera_calibration.npz",
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion_coefficients,
    )
    np.savez(
        data_dir / "camera_extrinsics.npz",
        rotation_vector=rotation_vector,
        translation_vector=translation_vector,
    )

    # Setup
    transformation_matrix = np.eye(3, dtype=np.float32)
    config = AppConfig(
        width=100,
        height=100,
        projector_matrix=transformation_matrix,
        storage_manager=storage,
    )
    app = InteractiveApp(config)

    # Create fake map
    map_name = "test_map.svg"
    map_file = tmp_path / map_name
    map_file.write_text('<svg width="100" height="100"></svg>')

    # Register map in config with ABSOLUTE path
    abs_path = str(map_file.resolve())
    app.map_config.data.maps[abs_path] = MapEntry(grid_spacing_svg=10.0)

    # Change dir to tmp_path to simulate relative path usage
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Call with RELATIVE path
        app.load_map(map_name)

        # Verify it found the config entry (which means it normalized the lookup key)
        # If it failed, it would not have loaded the grid params (we'd need to check logs or state)
        # But we can check if last_used_map is absolute
        assert app.map_config.data.global_settings.last_used_map == abs_path

    finally:
        os.chdir(cwd)
