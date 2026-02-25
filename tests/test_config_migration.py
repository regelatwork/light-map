import os
import json
import shutil
from light_map.map_config import MapConfigManager
from light_map.core.storage import StorageManager


def test_config_migration_to_tokens_json():
    # Setup: Create a temporary directory for config
    base_dir = "temp_test_config_migration"
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)

    storage = StorageManager(base_dir=base_dir)
    storage.ensure_dirs()

    map_state_path = storage.get_config_path("map_state.json")
    tokens_path = storage.get_config_path("tokens.json")

    old_data = {
        "global": {
            "projector_ppi": 105.0,
            "token_profiles": {"mega": {"size": 4, "height_mm": 100.0}},
            "aruco_defaults": {"101": {"name": "Migrated Token", "type": "NPC"}},
        },
        "maps": {},
    }

    with open(map_state_path, "w") as f:
        json.dump(old_data, f)

    # Ensure tokens.json does NOT exist
    assert not os.path.exists(tokens_path)

    # Act: Initialize MapConfigManager which should trigger migration
    manager = MapConfigManager(filename=map_state_path, storage=storage)

    # Assertions
    # 1. tokens.json should have been created
    assert os.path.exists(tokens_path), "tokens.json was not created"

    with open(tokens_path, "r") as f:
        tokens_data = json.load(f)
        assert "mega" in tokens_data.get("token_profiles", {})
        assert tokens_data["token_profiles"]["mega"]["size"] == 4
        assert tokens_data["aruco_defaults"]["101"]["name"] == "Migrated Token"

    # 2. Manager data should contain the migrated values
    assert "mega" in manager.data.global_settings.token_profiles
    assert manager.data.global_settings.token_profiles["mega"].size == 4
    assert 101 in manager.data.global_settings.aruco_defaults
    assert manager.data.global_settings.aruco_defaults[101].name == "Migrated Token"

    # 3. Check that save() does not put tokens back into map_state.json
    manager.save()
    with open(map_state_path, "r") as f:
        map_state_data = json.load(f)
        assert "token_profiles" not in map_state_data["global"]
        assert "aruco_defaults" not in map_state_data["global"]
        # Non-migrated global settings should remain
        assert map_state_data["global"]["projector_ppi"] == 105.0

    # 4. Verify that subsequent loads still work (reading from tokens.json)
    new_manager = MapConfigManager(filename=map_state_path, storage=storage)
    assert "mega" in new_manager.data.global_settings.token_profiles
    assert 101 in new_manager.data.global_settings.aruco_defaults

    # Cleanup
    shutil.rmtree(base_dir)


if __name__ == "__main__":
    test_config_migration_to_tokens_json()
