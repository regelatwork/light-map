import os
import numpy as np
from light_map.common_types import AppConfig
from light_map.interactive_app import InteractiveApp


def test_svg_loader_path_normalization(tmp_path):
    from light_map.svg_loader import SVGLoader

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
    m = np.eye(3, dtype=np.float32)
    config = AppConfig(
        width=640, height=480, projector_matrix=m, storage_manager=storage
    )
    app = InteractiveApp(config)

    assert app.map_system.width == 640
    assert app.map_system.height == 480

    new_config = AppConfig(width=1280, height=720, projector_matrix=m)
    app.reload_config(new_config)

    assert app.map_system.width == 1280
    assert app.map_system.height == 720


def test_token_tracker_determinism():
    from light_map.token_tracker import TokenTracker

    tracker = TokenTracker()

    _, pts1 = tracker.get_scan_pattern(1000, 1000, 100)
    _, pts2 = tracker.get_scan_pattern(1000, 1000, 100)

    assert pts1 == pts2


def test_interactive_app_load_map_normalization(tmp_path):
    from light_map.map_config import MapEntry
    from light_map.core.storage import StorageManager

    storage = StorageManager(base_dir=str(tmp_path))

    # Setup
    m = np.eye(3, dtype=np.float32)
    config = AppConfig(
        width=100, height=100, projector_matrix=m, storage_manager=storage
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
