import os
from light_map.map_config import MapConfigManager


def test_map_config_manager_aruco_defaults(tmp_path):
    # Use a temp directory to avoid picking up root tokens.json
    test_file = str(tmp_path / "test_map_state.json")

    manager = MapConfigManager(filename=test_file)

    # 1. Check initial defaults (now updated from root tokens.json)
    # The default for small is 37.0 from the current environment's config
    # but MapConfigManager inits with GlobalMapConfig defaults if no tokens.json exists in tmp_path.
    # GlobalMapConfig defaults are small=15, med=25, large=40, huge=60.
    # Wait, did I change GlobalMapConfig defaults?
    # I changed SizeProfile default height_mm to 50.0 but not the profiles in GlobalMapConfig.
    assert manager.data.global_settings.token_profiles["small"].height_mm == 15.0

    # 2. Add an ArUco default
    manager.set_global_aruco_definition(
        1, "Fighter", type="PC", profile="medium", color="#FF0000"
    )

    # 3. Add an ArUco override for a specific map
    map_name = "test_map.svg"
    # Setting height_mm will clear profile
    manager.set_map_aruco_override(
        map_name, 1, "Strong Fighter", type="PC", height_mm=30.0, color="#00FF00"
    )

    # 4. Resolve profiles
    resolved_global = manager.resolve_token_profile(1)
    assert resolved_global.name == "Fighter"
    assert resolved_global.height_mm == 25.0  # medium profile
    assert resolved_global.is_known is True
    assert resolved_global.color == "#FF0000"

    resolved_override = manager.resolve_token_profile(1, map_name)
    assert resolved_override.name == "Strong Fighter"
    assert resolved_override.height_mm == 30.0  # override
    assert resolved_override.is_known is True
    assert resolved_override.color == "#00FF00"

    # Verify profile was cleared by override
    override_def = manager.data.maps[os.path.abspath(map_name)].aruco_overrides[1]
    assert override_def.profile is None
    assert override_def.height_mm == 30.0


def test_map_config_manager_mutual_exclusivity(tmp_path):
    test_file = str(tmp_path / "test_state.json")
    manager = MapConfigManager(filename=test_file)

    # 1. Set profile -> should clear custom dimensions
    manager.set_global_aruco_definition(
        1, "Hero", profile="large", size=5, height_mm=100.0
    )
    defn = manager.data.global_settings.aruco_defaults[1]
    assert defn.profile == "large"
    assert defn.size is None
    assert defn.height_mm is None

    # 2. Set custom dimensions -> should clear profile
    manager.set_global_aruco_definition(1, "Hero", size=5, height_mm=100.0)
    defn = manager.data.global_settings.aruco_defaults[1]
    assert defn.profile is None
    assert defn.size == 5
    assert defn.height_mm == 100.0

    # 3. Repeat for map overrides
    map_name = "map.svg"
    manager.set_map_aruco_override(map_name, 1, "Boss", profile="huge", height_mm=200.0)
    override = manager.data.maps[os.path.abspath(map_name)].aruco_overrides[1]
    assert override.profile == "huge"
    assert override.height_mm is None

    manager.set_map_aruco_override(map_name, 1, "Boss", height_mm=200.0)
    override = manager.data.maps[os.path.abspath(map_name)].aruco_overrides[1]
    assert override.profile is None
    assert override.height_mm == 200.0

    # 5. Check all configs
    manager.set_global_aruco_definition(2, "Goblin", type="NPC", profile="small")
    configs = manager.get_aruco_configs(map_name)
    assert 1 in configs
    assert 2 in configs
    assert configs[1]["name"] == "Boss"
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
