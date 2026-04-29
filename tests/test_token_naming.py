import os

from light_map.core.common_types import NamingStyle
from light_map.core.token_naming import (
    NAMES_AMERICAN,
    NAMES_FANTASY,
    NAMES_SCI_FI,
    generate_token_name,
)
from light_map.map.map_config import MapConfigManager


def test_generate_token_name_stability():
    # Same ID and map name should produce same name
    name1 = generate_token_name(1, "test_map.svg", NamingStyle.SCI_FI)
    name2 = generate_token_name(1, "test_map.svg", NamingStyle.SCI_FI)
    assert name1 == name2

    # Different ID should produce different name (usually, but let's check)
    name3 = generate_token_name(2, "test_map.svg", NamingStyle.SCI_FI)
    assert name1 != name3

    # Different map name should produce different name
    name4 = generate_token_name(1, "other_map.svg", NamingStyle.SCI_FI)
    assert name1 != name4


def test_generate_token_name_styles():
    aruco_id = 42
    map_name = "dungeon.svg"

    # Numbered
    name = generate_token_name(aruco_id, map_name, NamingStyle.NUMBERED)
    assert name == f"Unknown Token #{aruco_id}"

    # Sci-Fi (Default)
    name = generate_token_name(aruco_id, map_name, NamingStyle.SCI_FI)
    base_name = name.split(" (")[0]
    assert base_name in NAMES_SCI_FI
    assert f"({aruco_id})" in name

    # Fantasy
    name = generate_token_name(aruco_id, map_name, NamingStyle.FANTASY)
    base_name = name.split(" (")[0]
    assert base_name in NAMES_FANTASY
    assert f"({aruco_id})" in name

    # American
    name = generate_token_name(aruco_id, map_name, NamingStyle.AMERICAN)
    base_name = name.split(" (")[0]
    assert base_name in NAMES_AMERICAN
    assert f"({aruco_id})" in name


def test_map_config_manager_naming_integration():
    test_file = "test_naming_state.json"
    if os.path.exists(test_file):
        os.remove(test_file)

    manager = MapConfigManager(filename=test_file)

    # Default should be SCI_FI
    assert manager.data.global_settings.naming_style == NamingStyle.SCI_FI

    aruco_id = 10
    map_name = "test.svg"

    # Resolve unknown token
    resolved = manager.resolve_token_profile(aruco_id, map_name)
    base_name = resolved.name.split(" (")[0]
    assert base_name in NAMES_SCI_FI
    assert f"({aruco_id})" in resolved.name

    # Change style to FANTASY
    manager.data.global_settings.naming_style = NamingStyle.FANTASY
    resolved = manager.resolve_token_profile(aruco_id, map_name)
    base_name = resolved.name.split(" (")[0]
    assert base_name in NAMES_FANTASY

    # Change style to NUMBERED
    manager.data.global_settings.naming_style = NamingStyle.NUMBERED
    resolved = manager.resolve_token_profile(aruco_id, map_name)
    assert resolved.name == f"Unknown Token #{aruco_id}"

    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)


def test_map_config_manager_naming_serialization():
    test_file = "test_naming_serialize.json"
    if os.path.exists(test_file):
        os.remove(test_file)

    manager = MapConfigManager(filename=test_file)
    manager.set_naming_style(NamingStyle.FANTASY)

    # Reload from file
    manager2 = MapConfigManager(filename=test_file)
    assert manager2.get_naming_style() == NamingStyle.FANTASY

    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)
