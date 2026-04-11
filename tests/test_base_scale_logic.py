import pytest
import numpy as np
import os
from light_map.core.common_types import AppConfig
from light_map.interactive_app import InteractiveApp


@pytest.fixture
def app(tmp_path, monkeypatch):
    from light_map.core.storage import StorageManager

    storage = StorageManager(base_dir=str(tmp_path))

    # Mock _load_camera_calibration
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


def test_base_scale_updates_on_load(app, tmp_path):
    map_path = os.path.join(str(tmp_path), "test_map.svg")
    with open(map_path, "w") as f:
        f.write(
            '<svg width="1000" height="1000"><rect x="0" y="0" width="100" height="100" /></svg>'
        )

    # 1. Calibrate grid: 100 SVG units = 1 inch. At 100 PPI, base_scale should be 1.0.
    app.map_config.save_map_grid_config(
        map_path,
        grid_spacing_svg=100.0,
        grid_origin_svg_x=0.0,
        grid_origin_svg_y=0.0,
        physical_unit_inches=1.0,
        scale_factor_1to1=1.0,
    )

    # 2. Load map.
    app.load_map(map_path)
    assert app.map_system.base_scale == 1.0

    # 3. Change PPI to 50. Base scale should be (1*50)/100 = 0.5.
    app.map_config.set_ppi(50.0)
    app.load_map(map_path)
    assert app.map_system.base_scale == 0.5

    # 4. Zoom to 2.0 and reset.
    app.map_system.state.zoom = 2.0
    app.map_system.reset_zoom_to_base()
    assert app.map_system.state.zoom == 0.5
