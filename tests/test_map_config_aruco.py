import os
from light_map.map_config import MapConfigManager


def test_map_config_manager_aruco_defaults(tmp_path):
    # Use a temp directory to avoid picking up root tokens.json
    test_file = str(tmp_path / "test_map_state.json")

    manager = MapConfigManager(filename=test_file)

    # 1. Check initial defaults
    assert manager.data.global_settings.token_profiles["small"].height_mm == 15.0

    # 2. Add an ArUco default
    manager.set_global_aruco_definition(1, "Fighter", type="PC", profile="medium")

    # 3. Add an ArUco override for a specific map
    map_name = "test_map.svg"
    manager.set_map_aruco_override(
        map_name, 1, "Strong Fighter", type="PC", height_mm=30.0
    )

    # 4. Resolve profiles
    resolved_global = manager.resolve_token_profile(1)
    assert resolved_global.name == "Fighter"
    assert resolved_global.height_mm == 25.0  # medium profile
    assert resolved_global.is_known is True

    resolved_override = manager.resolve_token_profile(1, map_name)
    assert resolved_override.name == "Strong Fighter"
    assert resolved_override.height_mm == 30.0  # override
    assert resolved_override.is_known is True

    # 5. Check all configs
    manager.set_global_aruco_definition(2, "Goblin", type="NPC", profile="small")
    configs = manager.get_aruco_configs(map_name)
    assert 1 in configs
    assert 2 in configs
    assert configs[1]["name"] == "Strong Fighter"
    assert configs[2]["name"] == "Goblin"

    # 6. Check unknown ID
    from light_map.common_types import NamingStyle

    manager.data.global_settings.naming_style = NamingStyle.NUMBERED
    unknown = manager.resolve_token_profile(99)
    assert "Unknown Token #99" == unknown.name
    assert unknown.is_known is False

    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)


if __name__ == "__main__":
    test_map_config_manager_aruco_defaults()
