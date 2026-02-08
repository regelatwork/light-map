import pytest
import json
from light_map.map_config import MapConfigManager


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
