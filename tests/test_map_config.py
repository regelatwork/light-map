import json

import pytest

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
    with open(temp_config_file) as f:
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


def test_aruco_defaults_and_overrides(tmp_path):
    import os

    config_file = str(tmp_path / "map_state.json")
    tokens_file = str(tmp_path / "tokens.json")

    # 1. Setup tokens.json with string keys
    tokens_data = {
        "token_profiles": {"small": {"size": 1, "height_mm": 15.0}},
        "aruco_defaults": {
            "42": {
                "name": "Global Token",
                "type": "NPC",
                "profile": "small",
                "color": "red",
            }
        },
    }
    with open(tokens_file, "w") as f:
        json.dump(tokens_data, f)

    # 2. Setup map_state.json with map override (string keys in JSON)
    map_abs_path = os.path.abspath("test.svg")
    state_data = {
        "global": {"projector_ppi": 100.0},
        "maps": {
            map_abs_path: {
                "aruco_overrides": {
                    "42": {"name": "Map Override Token", "type": "PC", "size": 2}
                }
            }
        },
    }
    with open(config_file, "w") as f:
        json.dump(state_data, f)

    manager = MapConfigManager(config_file)

    # Verify Global Defaults (if resolved without map)
    resolved_global = manager.resolve_token_profile(42)
    assert resolved_global.name == "Global Token"
    assert resolved_global.type == "NPC"
    assert resolved_global.size == 1
    assert resolved_global.height_mm == 15.0
    assert resolved_global.color == "red"

    # Verify Map Overrides
    resolved_map = manager.resolve_token_profile(42, map_name=map_abs_path)
    assert resolved_map.name == "Map Override Token"
    assert resolved_map.type == "PC"
    assert resolved_map.size == 2
    assert (
        resolved_map.height_mm == 50.0
    )  # DEFAULT_TOKEN_HEIGHT_MM (override clears profile/custom if not set in override definition? wait.)
    assert (
        resolved_map.color is None
    )  # Overrides don't merge, they replace the definition
