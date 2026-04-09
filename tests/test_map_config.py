import pytest
import json
from light_map.map.map_config import MapConfigManager


@pytest.fixture
def temp_config_file(tmp_path):
    p = tmp_path / "test_map_state.json"
    return str(p)


def test_load_defaults(temp_config_file):
    manager = MapConfigManager(temp_config_file)
    assert manager.get_ppi() == 96.0
    assert manager.data.maps == {}


def test_save_and_load(temp_config_file):
    manager = MapConfigManager(temp_config_file)
    manager.set_ppi(150.0)
    manager.save_map_viewport("test.svg", 10, 20, 2.0, 90)

    # Reload
    manager2 = MapConfigManager(temp_config_file)
    assert manager2.get_ppi() == 150.0

    vp = manager2.get_map_viewport("test.svg")
    assert vp.x == 10
    assert vp.y == 20
    assert vp.zoom == 2.0
    assert vp.rotation == 90


def test_persistence_format(temp_config_file):
    manager = MapConfigManager(temp_config_file)
    manager.set_ppi(100.0)

    # Check file content directly
    with open(temp_config_file, "r") as f:
        data = json.load(f)

    assert data["global"]["projector_ppi"] == 100.0


def test_save_numpy_types(temp_config_file):
    import numpy as np

    manager = MapConfigManager(temp_config_file)

    # Set PPI using a numpy float
    ppi_val = np.float32(123.45)
    manager.set_ppi(ppi_val)

    # Save Viewport using numpy floats
    manager.save_map_viewport(
        "test_map",
        np.float64(10.0),
        np.float64(20.0),
        np.float32(1.5),
        np.float32(90.0),
    )

    # Reload and check types/values
    manager2 = MapConfigManager(temp_config_file)
    assert manager2.get_ppi() == pytest.approx(123.45, abs=0.01)

    vp = manager2.get_map_viewport("test_map")
    assert vp.x == 10.0
    assert vp.y == 20.0
    assert vp.zoom == 1.5
    assert vp.rotation == 90.0
