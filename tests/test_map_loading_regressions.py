import pytest
import numpy as np
import os
from light_map.core.common_types import AppConfig
from light_map.interactive_app import InteractiveApp


@pytest.fixture
def app(tmp_path, monkeypatch):
    from light_map.core.storage import StorageManager

    storage = StorageManager(base_dir=str(tmp_path))

    # Mock _load_camera_calibration to avoid file system calls and sys.exit
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    config = AppConfig(
        width=1000, height=1000, projector_matrix=np.eye(3), storage_manager=storage
    )

    app = InteractiveApp(config)
    app.map_config.set_ppi(100.0)
    return app


def test_load_map_updates_base_scale_even_with_session(app, tmp_path):
    """
    Regression test for a bug where base_scale was not updated when a session was loaded,
    causing 'Reset Zoom 1:1' to use an incorrect (default) scale.
    """
    # 1. Create a dummy map file
    map_path = os.path.join(str(tmp_path), "test_map.svg")
    with open(map_path, "w") as f:
        f.write(
            '<svg width="1000" height="1000"><rect x="0" y="0" width="100" height="100" /></svg>'
        )

    # 2. Calibrate the grid for this map
    # 100 SVG units = 1 inch (at 100 PPI)
    app.map_config.save_map_grid_config(
        map_path,
        grid_spacing_svg=100.0,
        grid_origin_svg_x=0.0,
        grid_origin_svg_y=0.0,
        physical_unit_inches=1.0,
        scale_factor_1to1=1.0,
    )

    # 3. Create a session for this map
    session_dir = os.path.join(str(tmp_path), "sessions")
    os.makedirs(session_dir, exist_ok=True)

    from light_map.map.session_manager import SessionManager
    from light_map.core.common_types import ViewportState, SessionData

    session = SessionData(
        map_file=map_path,
        viewport=ViewportState(zoom=2.0),  # Zoomed in
        tokens=[],
        door_states={},
    )
    SessionManager.save_for_map(map_path, session, session_dir=session_dir)

    # 4. Load the map with session
    # Initial base_scale in map_system is 1.0.
    # Let's force it to 0.0 to ensure it gets updated.
    app.map_system.base_scale = 0.0

    app.load_map(map_path, load_session=True)

    # base_scale should now be (1.0 * 100.0) / 100.0 = 1.0
    assert app.map_system.base_scale == 1.0

    # 5. Now change PPI and check if it recalculates correctly on next load
    app.map_config.set_ppi(50.0)
    app.load_map(map_path, load_session=True)

    # base_scale should now be (1.0 * 50.0) / 100.0 = 0.5
    assert app.map_system.base_scale == 0.5

    # 6. Verify Reset Zoom 1:1 works using this scale
    # Pivot around center (500, 500)
    app.map_system.reset_zoom_to_base()
    assert app.map_system.state.zoom == 0.5
