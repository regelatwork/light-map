import pytest
import os
import json
from dataclasses import asdict
from light_map.map_config import MapConfigManager, GlobalMapConfig, MapEntry

# Define the new structures (for the test, until we implement them in src)
# Or better, just expect them to be available on MapConfigManager and its data structures.
# Since python is dynamic, I can write the test assuming the attributes exist.

@pytest.fixture
def temp_config_file(tmp_path):
    return str(tmp_path / "test_map_state_aruco.json")

def test_default_profiles_exist(temp_config_file):
    """Verify that a new config has default profiles."""
    manager = MapConfigManager(temp_config_file)
    profiles = manager.data.global_settings.token_profiles
    
    assert "small" in profiles
    assert profiles["small"].size == 1
    assert profiles["small"].height_mm == 15.0
    
    assert "medium" in profiles
    assert profiles["medium"].size == 1
    assert profiles["medium"].height_mm == 25.0

    assert "large" in profiles
    assert profiles["large"].size == 2
    assert profiles["large"].height_mm == 40.0
    
    assert "huge" in profiles
    assert profiles["huge"].size == 3
    assert profiles["huge"].height_mm == 60.0

def test_resolve_token_profile_basic(temp_config_file):
    """Test resolving a profile that is defined in global defaults."""
    manager = MapConfigManager(temp_config_file)
    
    # Manually add a default for ID 10 -> Goblin (Small)
    # Note: We need to use the actual class structure once implemented.
    # For now, we assume helper methods or direct access.
    
    # Let's assume a helper method to add definitions for testing
    manager.set_global_aruco_definition(10, name="Goblin", type="NPC", profile="small")
    
    profile = manager.resolve_token_profile(10)
    assert profile.name == "Goblin"
    assert profile.height_mm == 15.0
    assert profile.size == 1

def test_resolve_token_profile_explicit_dimensions(temp_config_file):
    """Test resolving a profile with explicit dimensions."""
    manager = MapConfigManager(temp_config_file)
    
    manager.set_global_aruco_definition(99, name="Custom", type="PC", size=2, height_mm=32.5)
    
    profile = manager.resolve_token_profile(99)
    assert profile.name == "Custom"
    assert profile.height_mm == 32.5
    assert profile.size == 2

def test_resolve_token_profile_override(temp_config_file):
    """Test map-specific override."""
    manager = MapConfigManager(temp_config_file)
    map_name = "/abs/path/to/dungeon.svg"
    
    # Global: ID 10 is Small Goblin
    manager.set_global_aruco_definition(10, name="Goblin", type="NPC", profile="small")
    
    # Map Override: ID 10 is Boss Goblin (Medium)
    manager.set_map_aruco_override(map_name, 10, name="Boss Goblin", type="NPC", profile="medium")
    
    # Resolve without map -> Small
    p_global = manager.resolve_token_profile(10)
    assert p_global.name == "Goblin"
    assert p_global.height_mm == 15.0
    
    # Resolve with map -> Medium
    p_map = manager.resolve_token_profile(10, map_name=map_name)
    assert p_map.name == "Boss Goblin"
    assert p_map.height_mm == 25.0

def test_resolve_token_fallback(temp_config_file):
    """Test fallback for unknown ID."""
    manager = MapConfigManager(temp_config_file)
    
    # ID 123 is unknown
    p = manager.resolve_token_profile(123)
    assert p.name == "Unknown Token #123"
    assert p.height_mm == 10.0 # Generic default
    assert p.size == 1

def test_persistence_aruco(temp_config_file):
    """Test saving and loading ArUco configs."""
    manager = MapConfigManager(temp_config_file)
    
    manager.set_global_aruco_definition(50, name="Dragon", type="NPC", profile="huge")
    manager.set_map_aruco_override("test.svg", 50, name="Weak Dragon", type="NPC", profile="small")
    
    # Reload
    manager2 = MapConfigManager(temp_config_file)
    
    p_global = manager2.resolve_token_profile(50)
    assert p_global.name == "Dragon"
    assert p_global.height_mm == 60.0
    
    p_map = manager2.resolve_token_profile(50, map_name="test.svg")
    assert p_map.name == "Weak Dragon"
    assert p_map.height_mm == 15.0
