import pytest
from unittest.mock import MagicMock
import numpy as np
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import GestureType, AppMode, MenuItem

@pytest.fixture
def app():
    # Minimal Setup
    config = AppConfig(
        width=100, height=100,
        projector_matrix=np.eye(3),
        root_menu=MenuItem("Root")
    )
    app = InteractiveApp(config)
    app.mode = AppMode.MAP
    # Mock map system state
    app.map_system.state.x = 0
    app.map_system.state.y = 0
    app.map_system.state.zoom = 1.0
    return app

def test_zoom_grabbing_symmetric(app):
    # Hands at (40, 50) and (60, 50). Dist=20. Center=(50, 50)
    # Move to (30, 50) and (70, 50). Dist=40. Center=(50, 50)
    
    # 1. Start Zoom
    hands_start = [
        {"gesture": GestureType.POINTING, "proj_pos": (40, 50), "raw_landmarks": MagicMock()},
        {"gesture": GestureType.POINTING, "proj_pos": (60, 50), "raw_landmarks": MagicMock()},
    ]
    
    # Init time
    app.time_provider = MagicMock(return_value=1.0)
    app._process_map_mode(hands_start, 1.0)
    
    # Wait delay
    app._process_map_mode(hands_start, 2.0) # Trigger start logic
    
    assert app.zoom_start_dist == 20.0
    # World center under (50, 50) with Pan=0, Zoom=1 is (50, 50)
    assert app.zoom_start_world_center == (50.0, 50.0)
    
    # 2. Update Zoom (Symmetric expansion)
    hands_end = [
        {"gesture": GestureType.POINTING, "proj_pos": (30, 50), "raw_landmarks": MagicMock()},
        {"gesture": GestureType.POINTING, "proj_pos": (70, 50), "raw_landmarks": MagicMock()},
    ]
    
    app._process_map_mode(hands_end, 2.1)
    
    # Check Zoom
    assert app.map_system.state.zoom == 2.0
    
    # Check Pan
    # Center (50, 50) should still map to World (50, 50)
    # 50 = 50 * 2.0 + PanX => PanX = -50
    assert app.map_system.state.x == -50.0
    assert app.map_system.state.y == -50.0 # Y center was 50, now 50. 50 = 50*2 + PanY

def test_zoom_grabbing_asymmetric_fixed_hand(app):
    # Hands at (40, 50) and (60, 50). Dist=20.
    # Keep Right Hand fixed at (60, 50).
    # Move Left Hand to (20, 50). Dist=40.
    # New Center = (40, 50).
    
    # 1. Start
    hands_start = [
        {"gesture": GestureType.POINTING, "proj_pos": (40, 50), "raw_landmarks": MagicMock()},
        {"gesture": GestureType.POINTING, "proj_pos": (60, 50), "raw_landmarks": MagicMock()},
    ]
    app.time_provider = MagicMock(return_value=1.0)
    app._process_map_mode(hands_start, 1.0)
    app._process_map_mode(hands_start, 2.0)
    
    # 2. Update (Left moves left)
    hands_end = [
        {"gesture": GestureType.POINTING, "proj_pos": (20, 50), "raw_landmarks": MagicMock()},
        {"gesture": GestureType.POINTING, "proj_pos": (60, 50), "raw_landmarks": MagicMock()},
    ]
    
    app._process_map_mode(hands_end, 2.1)
    
    # Check Zoom
    assert app.map_system.state.zoom == 2.0
    
    # Check Pan
    # New Screen Center = (40, 50)
    # Old World Center = (50, 50)
    # 40 = 50 * 2.0 + PanX => PanX = -60
    assert app.map_system.state.x == -60.0
    
    # Verification: Right Hand point
    # World Point under Right Hand (60, 50) at start was (60, 50)
    # New Screen Pos = World(60) * 2.0 + Pan(-60) = 120 - 60 = 60.
    # Matches! Right hand stays fixed on map.
    
    # Left Hand point
    # World Point under Left Hand (40, 50) at start was (40, 50)
    # New Screen Pos = World(40) * 2.0 + Pan(-60) = 80 - 60 = 20.
    # Matches! Left hand stays fixed on map.
